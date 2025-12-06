import os
import re
import textwrap
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, List, Tuple, Optional

import streamlit as st
import streamlit.components.v1 as components

from components.sidebar import render_sidebar
from workflow.graph import create_lego_graph
from workflow.state import LegoState

from utils.rebrickable_client import RebrickableClient
from components.brick_table import build_brick_table_html


def setup_logging() -> None:
    """콘솔 + 파일(app/logs/app.log)로 로깅 설정.
    Streamlit 재실행 시 중복 핸들러 추가를 피하기 위해 한 번만 설정.
    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(base_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "app.log")

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        root_logger.warning("로그 파일 설정 중 예외 발생: %s", e)


setup_logging()
logger = logging.getLogger(__name__)


st.set_page_config(
    page_title="레고 창작 AI Agent (Multi-Agent + RAG)",
    page_icon="🧱",
    layout="wide",
)


@st.cache_resource
def get_graph():
    return create_lego_graph()


def build_user_input(goal: str, sidebar_state: Dict[str, Any]) -> str:
    lines = [
        "[창작 목표]",
        goal.strip() or "미입력",
        "",
        "[전반 정보]",
        f"- 규모: {sidebar_state.get('scale', '')}",
        f"- 용도: {sidebar_state.get('usage', '')}",
        f"- 난이도 선호: {sidebar_state.get('difficulty', '')}",
        "",
        "[보유 색상/테마]",
        sidebar_state.get("colors", "").strip() or "미입력",
        "",
        "[보유 브릭/부품 정보]",
        sidebar_state.get("parts", "").strip() or "미입력",
        "",
        "[제약 조건 / 추가 요청]",
        sidebar_state.get("constraints", "").strip() or "미입력",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------
# 5. 브릭/부품 제안 섹션 파싱 유틸
# ------------------------------------------------------------
def split_brick_section(answer: str) -> Tuple[str, str, str]:
    """전체 답변에서 '5. 브릭/부품 제안' 섹션만 분리."""
    pattern = r"^\s*(?:[#*]+\s*)?5\.\s*브릭\s*/?\s*부품\s*제안.*$"

    match = re.search(pattern, answer, flags=re.MULTILINE)
    if not match:
        logger.info("[main] '브릭/부품 제안' 섹션 헤더를 찾지 못했습니다.")
        return answer, "", ""

    header_start = match.start()
    header_end = match.end()
    logger.info(
        "[main] 브릭/부품 제안 헤더 위치: start=%d, end=%d",
        header_start,
        header_end,
    )

    rest = answer[header_end:]
    next_sec_match = re.search(r"(?m)^\s*\d+\.\s", rest)
    if next_sec_match:
        section_end = header_end + next_sec_match.start()
    else:
        section_end = len(answer)

    before = answer[:header_start]
    brick_section = answer[header_start:section_end]
    after = answer[section_end:]

    logger.info(
        "[main] 브릭/부품 제안 섹션 분리 완료: before_len=%d, section_len=%d, after_len=%d",
        len(before),
        len(brick_section),
        len(after),
    )
    return before, brick_section, after


def _extract_first_part_num(text: str) -> str:
    """설명 문자열에서 LEGO 파트 번호로 보이는 첫 숫자 뽑기 (3~6자리)."""
    m = re.search(r"\b(\d{3,6})\b", text)
    if not m:
        return ""
    return m.group(1)


def parse_brick_rows_from_section(brick_section: str) -> List[Dict[str, Any]]:
    """
    브릭/부품 제안 섹션 텍스트에서 행(row) 리스트 추출.

    지원 포맷 예시:

    A) 4열 - 용도 / 부품 종류 및 색상 / 부품 번호 / 비고
       → part_type = 2열, part_num = 3열, description = 4열

    B) 3열 - 부품 종류 / 상세 예시 및 부품 번호 / 용도 및 특징
       → part_type = 1열, part_num = '상세 예시' 안 숫자, description = 3열

    어떤 포맷이든 최종적으로는
      part_type / part_num / description
    세 필드만 뽑아서 brick_table 로 넘긴다.
    """
    lines = brick_section.splitlines()
    if not lines:
        return []

    # 첫 줄은 '5. 브릭/부품 제안' 헤더일 가능성이 크니 건너뜀
    content_lines = [ln for ln in lines[1:] if ln.strip()]
    if not content_lines:
        return []

    # --- 헤더 행 찾기 ---
    header_idx = None
    for idx, line in enumerate(content_lines):
        stripped = line.strip()
        if "|" not in stripped:
            continue
        sep_candidate = stripped.replace("|", "").strip()
        if sep_candidate and set(sep_candidate) <= set("-: "):
            # --- 같은 구분선은 스킵
            continue
        header_idx = idx
        break

    if header_idx is None:
        logger.warning("[main] 브릭/부품 제안 섹션에서 테이블 헤더를 찾지 못했습니다.")
        return []

    header_line = content_lines[header_idx].strip()
    header_cells = [c.strip() for c in header_line.strip("|").split("|")]
    n_cols = len(header_cells)
    logger.info("[main] 브릭/부품 제안 테이블 헤더: %s", header_cells)

    # --- 포맷 판별 ---
    header_text = " ".join(header_cells)
    format_type = "type_first_detail_3"

    if n_cols >= 4 and "용도" in header_cells[0] and "부품 번호" in header_text:
        # 용도 / 부품 종류 및 색상 / 부품 번호 / 비고
        format_type = "usage_first_4"
    elif n_cols == 3 and (
        "상세 예시" in header_cells[1]
        or "상세 설명" in header_cells[1]
        or "상세 예시 및 부품 번호" in header_cells[1]
    ):
        # 부품 종류 / 상세 예시 및 부품 번호 / 용도 및 특징
        format_type = "type_first_detail_3"
    else:
        # 애매하면 3열 상세 포맷으로 처리 (안전하게 숫자 추출)
        if n_cols >= 3 and "상세" in header_cells[1]:
            format_type = "type_first_detail_3"
        elif n_cols >= 4:
            format_type = "usage_first_4"

    logger.info("[main] 브릭/부품 제안 테이블 포맷 판별: %s", format_type)

    # --- 데이터 행 파싱 ---
    rows: List[Dict[str, Any]] = []

    for line in content_lines[header_idx + 1 :]:
        stripped = line.strip()
        if not stripped or "|" not in stripped:
            continue
        sep_candidate = stripped.replace("|", "").strip()
        if sep_candidate and set(sep_candidate) <= set("-: "):
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]

        if format_type == "usage_first_4":
            # 기대: [용도, 부품 종류 및 색상, 부품 번호, 비고]
            if len(cells) < 4:
                logger.debug("[main] usage_first_4 포맷이지만 4셀 미만: %s", cells)
                continue
            usage = cells[0]
            part_type = cells[1]
            part_num = cells[2]
            description = cells[3] or usage
        else:  # type_first_detail_3
            # 기대: [부품 종류, 상세 예시 및 부품 번호, 용도 및 특징]
            if len(cells) < 3:
                logger.debug("[main] type_first_detail_3 포맷이지만 3셀 미만: %s", cells)
                continue
            part_type = cells[0]
            detail = cells[1]
            description = cells[2]
            part_num = _extract_first_part_num(detail)

        rows.append(
            {
                "part_type": part_type,
                "part_num": part_num,
                "description": description,
            }
        )

    logger.info("[main] 브릭/부품 제안 섹션 파싱된 행 수: %d", len(rows))
    return rows


def render_answer_with_brick_table(answer: str) -> None:
    """최종 답변을 렌더링하되,
    5. 브릭/부품 제안 부분은 Rebrickable API와 HTML 테이블로 재구성해서 보여준다.
    """
    before, brick_section, after = split_brick_section(answer)

    if not brick_section:
        st.markdown(answer)
        return

    brick_rows = parse_brick_rows_from_section(brick_section)

    section_lines = brick_section.splitlines()
    header_line = section_lines[0] if section_lines else "5. 브릭/부품 제안"

    if not brick_rows:
        logger.warning(
            "[main] 브릭/부품 제안 섹션 파싱 실패 → 원본 섹션 그대로 표시."
        )
        st.markdown(answer)
        return

    client = RebrickableClient()
    brick_table_html = build_brick_table_html(brick_rows, client)

    if before.strip():
        st.markdown(before)

    st.markdown(header_line)

    # HTML 표를 그대로 렌더링 (순서 고정: 부품 종류 / 부품 번호 / 부품 이름 / 이미지 / 설명 및 용도)
    components.html(brick_table_html, height=400, scrolling=True)

    if after.strip():
        st.markdown(after)


# ------------------------------------------------------------
# Streamlit 메인 UI
# ------------------------------------------------------------
def main() -> None:
    st.title("🧱 레고 창작 AI Agent")
    st.caption("LangGraph Multi-Agent + RAG + Azure OpenAI + Streamlit")

    sidebar_state = render_sidebar()

    st.markdown("### 1️⃣ 만들고 싶은 레고 창작을 설명해주세요")

    default_goal = textwrap.dedent(
        """
        예시)
        - 동대문 야간 풍경을 표현한 디오라마
        - 기어와 모터로 돌아가는 전통 시계 구조
        - 아이가 가지고 놀 수 있는 작은 로봇
        """
    ).strip()

    goal = st.text_area(
        "작품 아이디어(자유롭게):",
        value=default_goal,
        height=160,
    )

    st.markdown("### 2️⃣ AI에게 설계를 요청해보세요")

    col1, col2 = st.columns([1, 2])

    with col1:
        generate_button = st.button("🚀 레고 설계 제안 받기", type="primary")

    with col2:
        st.info(
            "버튼을 누르면, 입력하신 정보(아이디어/규모/용도/보유 브릭 등)와\n"
            "내부 레고 지식(RAG)을 바탕으로\n"
            "요구사항 분석 → 설계 생성 → 최종 정리까지 Multi-Agent가 순차적으로 수행합니다.",
            icon="🤖",
        )

    if "lego_response" not in st.session_state:
        st.session_state.lego_response = ""

    if generate_button:
        with st.spinner("LangGraph 에이전트들이 레고 창작 아이디어를 구상 중입니다..."):
            try:
                graph = get_graph()
                user_input = build_user_input(goal, sidebar_state)

                logger.info("[main] 사용자 입력:\n%s", user_input)

                initial_state: LegoState = {
                    "user_input": user_input,
                    "messages": [],
                    "docs": {},
                    "contexts": {},
                    "current_step": "START",
                    "prev_node": "",
                }

                result_state: Dict[str, Any] = graph.invoke(initial_state)
                answer = result_state.get("final_answer") or "결과를 생성하지 못했습니다."

                logger.info(
                    "[main] LangGraph 실행 완료. 최종 답변 길이: %d",
                    len(answer),
                )

                st.session_state.lego_response = answer
            except Exception as e:
                # 여기서 보는 스택트레이스는 Azure content filter 걸릴 때 나는 예외입니다.
                # 코드 문제는 아니고, 답변 내용이 필터에 걸리면 Azure 쪽에서 에러를 줍니다.
                logger.exception("[main] LangGraph 에이전트 호출 중 예외 발생")
                st.error(f"에이전트 호출 중 오류가 발생했습니다: {e}")

    st.markdown("### 3️⃣ AI 레고 창작 가이드")

    if st.session_state.lego_response:
        render_answer_with_brick_table(st.session_state.lego_response)
    else:
        st.caption("아직 결과가 없습니다. 왼쪽 설정을 조정하고 위의 버튼을 눌러보세요.")


if __name__ == "__main__":
    main()
