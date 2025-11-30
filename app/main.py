import textwrap
import streamlit as st

from components.sidebar import render_sidebar
from workflow.graph import create_lego_graph
from workflow.state import LegoState

st.set_page_config(
    page_title="레고 창작 AI Agent (Multi-Agent + RAG)",
    page_icon="🧱",
    layout="wide",
)


@st.cache_resource
def get_graph():
    return create_lego_graph()


def build_user_input(goal: str, sidebar_state: dict) -> str:
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


def main():
    st.title("🧱 레고 창작 AI Agent")
    st.caption("LangGraph Multi-Agent + RAG + Azure OpenAI + Streamlit")

    sidebar_state = render_sidebar()

    st.markdown("### 1️⃣ 만들고 싶은 레고 창작을 설명해주세요")
    default_goal = textwrap.dedent(
        """            예시)
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
        generate_button = st.button("🧱 레고 설계 제안 받기", type="primary")

    with col2:
        st.info(
            "버튼을 누르면, 입력하신 정보(아이디어/규모/용도/보유 브릭 등)와\n"
            "내부 레고 지식(RAG)을 바탕으로\n"
            "요구사항 분석 → 설계 생성 → 최종 정리까지 Multi-Agent가 순차적으로 수행합니다.",
            icon="💡",
        )

    if "lego_response" not in st.session_state:
        st.session_state.lego_response = ""

    if generate_button:
        with st.spinner("LangGraph 에이전트들이 레고 창작 아이디어를 구상 중입니다..."):
            try:
                graph = get_graph()
                user_input = build_user_input(goal, sidebar_state)
                initial_state: LegoState = {
                    "user_input": user_input,
                    "messages": [],
                    "docs": {},
                    "contexts": {},
                    "current_step": "START",
                    "prev_node": "",
                }
                result_state = graph.invoke(initial_state)
                answer = result_state.get("final_answer") or "결과를 생성하지 못했습니다."
                st.session_state.lego_response = answer
            except Exception as e:
                st.error(f"에이전트 호출 중 오류가 발생했습니다: {e}")

    st.markdown("### 3️⃣ AI 레고 창작 가이드")

    if st.session_state.lego_response:
        st.markdown(st.session_state.lego_response)
    else:
        st.caption("아직 결과가 없습니다. 왼쪽 설정을 조정하고 위의 버튼을 눌러보세요.")


if __name__ == "__main__":
    main()
