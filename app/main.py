import os
import re
import time
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
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

class KSTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, KST)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(timespec="seconds")


def setup_logging() -> None:
    """콘솔 + 파일(app/logs/app.log)로 로깅 설정.
    Streamlit 재실행 시 중복 핸들러 추가를 피하기 위해 한 번만 설정.
    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    root_logger.setLevel(logging.INFO)

    formatter = KSTFormatter(
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
# 공통 텍스트 정리 유틸 (보이는 '\n' 라인 제거)
# ------------------------------------------------------------
def _clean_visual_newline_lines(text: str) -> str:
    """
    답변 안에 '문자 그대로' '\\n' 이 한 줄로 들어간 경우,
    그 줄은 화면에 그대로 보이므로 제거해준다.
    (실제 줄바꿈 문자 '\n' 은 그대로 둔다)
    """
    if not text:
        return text
    lines = text.splitlines()
    filtered = [ln for ln in lines if ln.strip() != r"\n"]
    return "\n".join(filtered)


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

    새 표 형식 (우선 지원):
      | 부품 종류 | 부품 번호 | 부품 이름 | 이미지 | 설명 및 용도 |

    - 에이전트가 위 형식을 지키면 이 규칙으로 파싱
    - 그렇지 않은 경우에는 기존(레거시) 3~4열 포맷으로 최대한 해석
    """
    lines = brick_section.splitlines()
    if not lines:
        return []

    # 첫 줄은 보통 "5. 브릭/부품 제안" 헤더 → 내용에서 제외
    content_lines = [ln for ln in lines[1:] if ln.strip()]
    if not content_lines:
        return []

    # --- 헤더 행 찾기 ---
    header_idx = None
    for idx, line in enumerate(content_lines):
        stripped = line.strip()
        if "|" not in stripped:
            continue
        # 구분선(| --- | --- |)은 제외
        sep_candidate = stripped.replace("|", "").strip()
        if sep_candidate and set(sep_candidate) <= set("-: "):
            continue
        header_idx = idx
        break

    if header_idx is None:
        logger.warning("[main] 브릭/부품 제안 섹션에서 테이블 헤더를 찾지 못했습니다.")
        return []

    header_line = content_lines[header_idx].strip()
    header_cells = [c.strip() for c in header_line.strip("|").split("|")]
    n_cols = len(header_cells)
    header_text = " ".join(header_cells)

    logger.info("[main] 브릭/부품 헤더: %s", header_cells)

    # --- 새 표 형식인지 먼저 판별 ---
    is_new_standard = (
        any("부품 종류" in c for c in header_cells)
        and any("부품 번호" in c for c in header_cells)
        and any("부품 이름" in c for c in header_cells)
        and any("이미지" in c for c in header_cells)
        and ("설명" in header_text or "용도" in header_text)
    )

    rows: List[Dict[str, Any]] = []

    if is_new_standard:
        # ✅ 새 표 포맷: 부품 종류 / 부품 번호 / 부품 이름 / 이미지 / 설명 및 용도
        logger.info("[main] 새 표 형식(5열)으로 브릭 제안 파싱")

        # 각 컬럼 인덱스 찾기 (혹시 순서가 바뀌어도 이름으로 찾도록)
        def find_idx(keyword: str, default: int) -> int:
            for i, c in enumerate(header_cells):
                if keyword in c:
                    return i
            return default

        idx_type = find_idx("부품 종류", 0)
        idx_num = find_idx("부품 번호", 1 if n_cols > 1 else 0)
        idx_desc = find_idx("설명", n_cols - 1)

        for line in content_lines[header_idx + 1 :]:
            stripped = line.strip()
            if not stripped or "|" not in stripped:
                continue

            # 구분선 스킵
            sep_candidate = stripped.replace("|", "").strip()
            if sep_candidate and set(sep_candidate) <= set("-: "):
                continue

            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) < 3:  # 최소 3개는 있어야 의미 있음
                continue

            # 인덱스 범위 방어
            def safe_get(c_list, idx):
                return c_list[idx] if 0 <= idx < len(c_list) else ""

            part_type = safe_get(cells, idx_type)
            part_num = safe_get(cells, idx_num)
            description = safe_get(cells, idx_desc)

            # URL이 설명에 들어온 경우는 후처리에서 제거하므로 여기서는 그대로 둠
            rows.append(
                {
                    "part_type": part_type,
                    "part_num": part_num,
                    "description": description,
                }
            )

        logger.info("[main] 새 표 형식으로 파싱된 행 수: %d", len(rows))
        return rows

    # ------------------------------------------------------------
    # 이하: 레거시 3~4열 포맷 (예전 규칙) → 기존 코드 최대한 유지
    # ------------------------------------------------------------
    logger.info("[main] 레거시 표 형식으로 브릭 제안 파싱 시도")

    # 첫 줄은 '5. 브릭/부품 제안' 헤더일 가능성이 크니 건너뜀
    # 이미 content_lines 는 1줄 건너뛴 상태
    # header_idx 이후가 실제 데이터
    content_lines_after_header = content_lines
    header_line = content_lines_after_header[header_idx].strip()
    header_cells = [c.strip() for c in header_line.strip("|").split("|")]
    n_cols = len(header_cells)
    header_text = " ".join(header_cells)

    # --- 포맷 판별 (기존 로직) ---
    format_type = "type_first_detail_3"

    if n_cols >= 4 and "용도" in header_cells[0] and "부품 번호" in header_text:
        format_type = "usage_first_4"
    elif n_cols == 3 and (
        "상세 예시" in header_cells[1]
        or "상세 설명" in header_cells[1]
        or "상세 예시 및 부품 번호" in header_cells[1]
    ):
        format_type = "type_first_detail_3"
    else:
        if n_cols >= 3 and "상세" in header_cells[1]:
            format_type = "type_first_detail_3"
        elif n_cols >= 4:
            format_type = "usage_first_4"

    logger.info("[main] 브릭/부품 제안 레거시 포맷 판별: %s", format_type)

    def _extract_first_part_num(text: str) -> str:
        m = re.search(r"\b(\d{3,6}[a-zA-Z]?)\b", text)
        return m.group(1) if m else ""

    for line in content_lines_after_header[header_idx + 1 :]:
        stripped = line.strip()
        if not stripped or "|" not in stripped:
            continue
        sep_candidate = stripped.replace("|", "").strip()
        if sep_candidate and set(sep_candidate) <= set("-: "):
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]

        if format_type == "usage_first_4":
            if len(cells) < 4:
                continue
            usage = cells[0]
            part_type = cells[1]
            part_num = cells[2]
            description = cells[3] or usage
        else:  # type_first_detail_3
            if len(cells) < 3:
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

    logger.info("[main] 레거시 포맷으로 파싱된 행 수: %d", len(rows))
    return rows


def render_answer_with_brick_table(answer: str) -> None:
    """최종 답변을 렌더링하되,
    5. 브릭/부품 제안 부분은 Rebrickable API와 HTML 테이블로 재구성해서 보여준다.
    또한, 테이블 위/아래에 보이는 '\\n' 라인은 제거하고,
    5번 제목이 항상 보이도록 정리한다.
    """
    # 전체 답변을 5번 섹션 기준으로 분리
    before, brick_section, after = split_brick_section(answer)

    # 5번 섹션 자체가 없으면, 전체를 한 번 깨끗이 정리해서 바로 출력
    if not brick_section:
        st.markdown(_clean_visual_newline_lines(answer))
        return

    # 5번 섹션 안에서, 눈에 보이는 '\n' 라인은 제거하고
    # 의미 있는 라인만 남김
    raw_section_lines = brick_section.splitlines()
    section_lines = [
        ln for ln in raw_section_lines if ln.strip() and ln.strip() != r"\n"
    ]

    if not section_lines:
        logger.warning(
            "[main] 브릭/부품 제안 섹션이 비어 있음 → 전체 답변만 출력."
        )
        st.markdown(_clean_visual_newline_lines(answer))
        return

    # 첫 줄은 항상 '5. 브릭/부품 제안' 헤더가 되도록 보정
    header_line = section_lines[0]
    cleaned_brick_section = "\n".join(section_lines)

    # 테이블 파싱은 정리된 섹션 텍스트 기준으로 수행
    brick_rows = parse_brick_rows_from_section(cleaned_brick_section)

    if not brick_rows:
        logger.warning(
            "[main] 브릭/부품 제안 섹션 파싱 실패 → 원본 섹션 그대로 표시."
        )
        st.markdown(_clean_visual_newline_lines(answer))
        return

    # before/after 텍스트에서도 눈에 보이는 '\n' 라인은 제거
    before_clean = _clean_visual_newline_lines(before)
    after_clean = _clean_visual_newline_lines(after)

    client = RebrickableClient()
    brick_table_html = build_brick_table_html(brick_rows, client)

    if before_clean.strip():
        st.markdown(before_clean)

    # 👉 여기서 5번 제목이 항상 보이도록 출력
    st.markdown(header_line)

    # HTML 표를 그대로 렌더링 (순서 고정: 부품 종류 / 부품 번호 / 부품 이름 / 이미지 / 설명 및 용도)
    components.html(brick_table_html, height=400, scrolling=True)

    if after_clean.strip():
        st.markdown(after_clean)


AGENT_STEPS = [
    ("requirements_agent", "요구사항 분석"),
    ("design_agent", "설계 생성"),
    ("refiner_agent", "최종 정리"),
]


def run_agents_streaming(goal: str, sidebar_state: Dict[str, Any]) -> str:
    """LangGraph를 스트리밍으로 실행.

    - 단계(에이전트)가 끝날 때마다 진행 상태를 갱신
    - 마지막 '최종 정리' 에이전트의 답변은 토큰 단위로 바로 화면에 표시
    성공 시 최종 답변, 실패 시 빈 문자열 반환
    """
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

    node_index = {name: i for i, (name, _) in enumerate(AGENT_STEPS)}
    total = len(AGENT_STEPS)
    final_node = AGENT_STEPS[-1][0]

    status = st.status(f"{AGENT_STEPS[0][1]} 중... (1/{total})", expanded=False)
    live = st.empty()  # 최종 정리 답변 실시간 표시용

    started = time.perf_counter()
    streamed = ""
    answer = ""
    step_chars = 0          # 현재 단계에서 생성된 글자 수 (진행 표시용)
    last_ui = 0.0

    try:
        for mode, chunk in graph.stream(initial_state, stream_mode=["updates", "messages"]):
            if mode == "messages":
                msg, meta = chunk
                node = meta.get("langgraph_node")
                if not (isinstance(msg.content, str) and msg.content):
                    continue
                if node == final_node:
                    streamed += msg.content
                    live.markdown(streamed + " ▌")
                elif node in node_index:
                    # 중간 단계도 진행 상황을 주기적으로 갱신
                    # (Streamlit은 화면 갱신 시점에만 중지 요청을 확인하므로, 중지 반응성 확보 목적도 있음)
                    step_chars += len(msg.content)
                    now = time.perf_counter()
                    if now - last_ui > 0.5:
                        last_ui = now
                        i = node_index[node]
                        status.update(label=f"{AGENT_STEPS[i][1]} 중... ({i + 1}/{total}) · {step_chars:,}자 작성 · {now - started:.0f}초")
                continue

            # mode == "updates": 노드 하나가 끝남
            for node, update in chunk.items():
                if node not in node_index:
                    continue
                idx = node_index[node]
                elapsed = time.perf_counter() - started
                status.write(f"✅ {AGENT_STEPS[idx][1]} 완료 ({elapsed:.0f}초)")
                logger.info("[main] %s 완료 (%.1fs)", node, elapsed)
                step_chars = 0

                if node == final_node:
                    answer = (update or {}).get("final_answer", "") or streamed
                elif idx + 1 < total:
                    nxt = AGENT_STEPS[idx + 1][1]
                    hint = " — 답변이 아래에 실시간으로 표시됩니다" if idx + 1 == total - 1 else ""
                    status.update(label=f"{nxt} 중... ({idx + 2}/{total}){hint}")

        elapsed = time.perf_counter() - started
        if not answer:
            answer = "결과를 생성하지 못했습니다."
        status.update(label=f"완료 ({elapsed:.0f}초)", state="complete")
        logger.info("[main] LangGraph 실행 완료 (%.1fs). 최종 답변 길이: %d", elapsed, len(answer))
        live.empty()  # 실시간 미리보기는 지우고, 아래에서 브릭 표 포함 최종 렌더링
        return answer

    except Exception as e:
        # 여기서 보는 스택트레이스는 Azure content filter 걸릴 때 나는 예외입니다.
        # 코드 문제는 아니고, 답변 내용이 필터에 걸리면 Azure 쪽에서 에러를 줍니다.
        logger.exception("[main] LangGraph 에이전트 호출 중 예외 발생")
        status.update(label="오류 발생", state="error")
        live.empty()
        st.error(f"에이전트 호출 중 오류가 발생했습니다: {e}")
        return ""


def _show_image(slot, data: Dict[str, Any]) -> None:
    with slot.container():
        if data.get("error"):
            st.warning(f"완성 예상 이미지를 만들지 못했습니다: {data['error']}")
            return
        st.image(data["png"], width="stretch")
        st.caption("⚠️ AI가 그린 **예상 이미지**입니다. 실제 부품 구성·도안과 다를 수 있습니다.")
        with st.expander("이미지 생성에 사용한 프롬프트"):
            st.code(data.get("prompt", ""), language=None, wrap_lines=True)


def _show_blueprint(slot, data: Dict[str, Any]) -> None:
    with slot.container():
        if data.get("error"):
            st.warning(f"조립 도안을 만들지 못했습니다: {data['error']}")
            return
        st.caption(f"📐 {data['summary']} · 브릭에 마우스를 올리면 크기/색/부품 번호가 보입니다.")
        for w in data.get("warnings", []):
            st.warning(w, icon="⚠️")
        components.html(data["html"], height=data["height"], scrolling=True)


VISUAL_LABELS = {"blueprint": "층별 조립 도안", "image": "완성 예상 이미지"}


def start_visuals(answer: str) -> Dict[str, Any]:
    """이미지(A)/도안(B) 생성을 백그라운드 스레드에서 즉시 시작.
    (부품 표 렌더링 - Rebrickable 조회 - 과 병렬로 진행되도록 가이드 렌더링 전에 호출)
    반환: {"futures": {Future: name}, "started": t}
    """
    from concurrent.futures import ThreadPoolExecutor
    from utils import image_gen
    from utils.blueprint import build_blueprint

    def make_image(text: str) -> Dict[str, Any]:
        png, prompt = image_gen.generate_preview(text)
        return {"png": png, "prompt": prompt}

    jobs = {"blueprint": build_blueprint}
    if image_gen.is_enabled():
        jobs["image"] = make_image

    pool = ThreadPoolExecutor(max_workers=len(jobs))
    futures = {pool.submit(fn, answer): name for name, fn in jobs.items()}
    pool.shutdown(wait=False)  # 작업은 계속 진행, 결과는 render_visuals 에서 수집
    return {"futures": futures, "started": time.perf_counter()}


def render_visuals(pending: Optional[Dict[str, Any]] = None) -> None:
    """완성 예상 이미지(A)와 층별 조립 도안(B) 표시.

    pending 이 있으면(새로 생성 중) 끝나는 순서대로 표시하며 session_state 에 저장,
    없으면(재실행) session_state 에 저장된 결과만 다시 표시.
    """
    from concurrent.futures import FIRST_COMPLETED, wait
    from utils import image_gen

    visuals: Dict[str, Any] = st.session_state.visuals
    image_on = image_gen.is_enabled()

    tab_bp, tab_img = st.tabs(["📐 층별 조립 도안", "🖼️ 완성 예상 이미지"])
    with tab_bp:
        bp_slot = st.empty()
    with tab_img:
        img_slot = st.empty()

    if not image_on:
        img_slot.info("이미지 모델이 설정되지 않았습니다 (.env 의 AOAI_DEPLOY_IMAGE).")

    slots = {"blueprint": (bp_slot, _show_blueprint), "image": (img_slot, _show_image)}

    if not pending:
        if "blueprint" in visuals:
            _show_blueprint(bp_slot, visuals["blueprint"])
        else:
            bp_slot.caption("설계 제안을 새로 받으면 조립 도안이 생성됩니다.")
        if image_on and "image" in visuals:
            _show_image(img_slot, visuals["image"])
        return

    futures = dict(pending["futures"])
    started = pending["started"]

    # 0.5초마다 경과 시간 갱신 (진행 표시 + 중지 요청 반응성 확보), 끝나는 순서대로 표시
    while futures:
        done, _ = wait(futures, timeout=0.5, return_when=FIRST_COMPLETED)
        for fut in done:
            name = futures.pop(fut)
            slot, show = slots[name]
            try:
                data = fut.result()
            except Exception as e:
                logger.exception("[main] %s 생성 실패", VISUAL_LABELS[name])
                data = {"error": str(e)[:300]}
            logger.info("[main] %s 완료 (%.1fs)", VISUAL_LABELS[name], time.perf_counter() - started)
            visuals[name] = data
            show(slot, data)
        elapsed = time.perf_counter() - started
        for name in futures.values():
            slots[name][0].info(f"⏳ {VISUAL_LABELS[name]}을(를) 만드는 중입니다... ({elapsed:.0f}초)")


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
        stop_slot = st.empty()
        if generate_button:
            # 실행 중에만 보이는 중지 버튼: 누르면 Streamlit이 현재 실행을 중단하고 다시 실행함
            # (작업이 모두 끝나면 아래에서 stop_slot.empty() 로 제거)
            stop_slot.button("⏹ 중지", key="stop_btn",
                             on_click=lambda: st.session_state.update(stopped=True))

    with col2:
        st.info(
            "버튼을 누르면, 입력하신 정보(아이디어/규모/용도/보유 브릭 등)와\n"
            "내부 레고 지식(RAG)을 바탕으로\n"
            "요구사항 분석 → 설계 생성 → 최종 정리까지 Multi-Agent가 순차적으로 수행합니다.",
            icon="🤖",
        )

    if "lego_response" not in st.session_state:
        st.session_state.lego_response = ""
    if "visuals" not in st.session_state:
        st.session_state.visuals = {}

    st.markdown("### 3️⃣ AI 레고 창작 가이드")

    if st.session_state.pop("stopped", False):
        logger.info("[main] 사용자가 요청을 중지함")
        st.info("⏹ 요청을 중지했습니다. 아래에는 직전 결과가 표시됩니다.")

    pending = None
    if generate_button:
        answer = run_agents_streaming(goal, sidebar_state)
        if answer:
            st.session_state.lego_response = answer
            st.session_state.visuals = {}  # 새 답변이 나왔을 때만 이전 이미지/도안 초기화 (중지 시 직전 결과 유지)
            # 이미지/도안 생성을 먼저 백그라운드로 시작 → 아래 부품 표(Rebrickable 조회)와 병렬 진행
            pending = start_visuals(answer)

    if not st.session_state.lego_response:
        stop_slot.empty()
        st.caption("아직 결과가 없습니다. 왼쪽 설정을 조정하고 위의 버튼을 눌러보세요.")
        return

    render_answer_with_brick_table(st.session_state.lego_response)

    # 4️⃣ 가이드 아래에 이미지/도안 표시 (사용자는 가이드를 읽으며 대기)
    st.markdown("### 4️⃣ 완성 예상 이미지 · 층별 조립 도안")
    render_visuals(pending)
    stop_slot.empty()  # 모든 작업 완료 → 중지 버튼 제거


if __name__ == "__main__":
    main()
