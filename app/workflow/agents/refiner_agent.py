from workflow.agents.base_agent import BaseLegoAgent
from workflow.state import LegoState, AgentRole
from utils.prompt import REFINER_AGENT_PROMPT


class RefinerAgent(BaseLegoAgent):
    """최종 설계 문서를 정리하는 에이전트"""

    def __init__(self, k: int = 1):
        super().__init__(role=AgentRole.REFINER, k=k)

    def get_system_prompt(self) -> str:
        return REFINER_AGENT_PROMPT

    def build_user_message(self, state: LegoState, context: str) -> str:
        requirements_summary = ""
        design_draft = ""
        for m in state.get("messages", []):
            if m.get("role") == AgentRole.REQUIREMENTS:
                requirements_summary = m.get("content", "")
            elif m.get("role") == AgentRole.DESIGN:
                design_draft = m.get("content", "")

        return (
            "다음은 레고 창작 요구사항 분석 결과와 설계 초안입니다.\n"
            "이를 통합하여 최종 레고 설계 가이드를 작성하세요.\n\n"
            "## 요구사항 분석 결과\n"
            f"{requirements_summary if requirements_summary else '요구사항 분석 결과가 없습니다.'}\n\n"
            "## 설계 초안\n"
            f"{design_draft if design_draft else '설계 초안이 없습니다.'}\n\n"
            "## 참고 지식 (선택적)\n"
            f"{context if context else '추가 참고 지식이 없습니다.'}"
        )

    def run(self, state: LegoState) -> LegoState:
        # 기본 run으로 상태 업데이트
        new_state = super().run(state)
        # 마지막 메시지를 final_answer로 저장
        if new_state.get("messages"):
            last = new_state["messages"][-1]
            new_state["final_answer"] = last.get("content", "")
        return new_state
