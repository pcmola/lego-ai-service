import streamlit as st


def render_sidebar() -> dict:
    """레고 창작 설정 사이드바"""

    with st.sidebar:
        st.subheader("⚙️ 레고 창작 설정")

        mode = st.radio(
            "어떤 도움을 받고 싶나요?",
            options=[
                "아이디어부터 전체 설계 제안",
                "이미 생각해둔 아이디어를 구체화",
            ],
            index=0,
        )

        st.markdown("---")

        scale = st.selectbox(
            "작품 규모",
            [
                "소형 (16x16 베이스 안쪽 / 손바닥 크기)",
                "중형 (32x32 / 선반 위 전시용)",
                "대형 (기성 진열장 한 칸 이상)",
            ],
            index=1,
        )

        usage = st.selectbox(
            "주 용도",
            [
                "전시용 (안정성과 디테일 위주)",
                "놀이용 (내구성과 플레이 기능 위주)",
                "전시 + 놀이 겸용",
            ],
            index=0,
        )

        difficulty = st.select_slider(
            "난이도 선호",
            options=["입문자", "중급", "상급"],
            value="중급",
        )

        st.markdown("---")

        st.markdown("**보유 브릭 정보 (선택)**")
        colors = st.text_area(
            "주요 색상/테마",
            value="예: 흰색/회색 브릭 많음, 파란 타일 조금, 투명 브릭 약간",
            height=70,
        )

        parts = st.text_area(
            "특이 부품",
            value="예: 테크닉 빔/핀 약간, 톱니바퀴 몇 개, 미니피겨 3명",
            height=70,
        )

        st.markdown("---")
        constraints = st.text_area(
            "제약 조건 / 추가 요청",
            value="예: 높이 25cm 이내, 아이가 만져도 쉽게 안 부서졌으면 좋겠어요.",
            height=80,
        )

    return {
        "mode": mode,
        "scale": scale,
        "usage": usage,
        "difficulty": difficulty,
        "colors": colors,
        "parts": parts,
        "constraints": constraints,
    }
