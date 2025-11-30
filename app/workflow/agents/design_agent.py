from workflow.agents.base_agent import BaseLegoAgent
from workflow.state import LegoState, AgentRole
from utils.prompt import DESIGN_AGENT_PROMPT


class DesignAgent(BaseLegoAgent):
    """레고 설계 생성 에이전트"""

    def __init__(self, k: int = 4):
        super().__init__(role=AgentRole.DESIGN, k=k)

    def get_system_prompt(self) -> str:
        return DESIGN_AGENT_PROMPT

    def build_user_message(self, state: LegoState, context: str) -> str:
        # 이전 요구사항 분석 결과를 messages에서 찾아 사용
        requirements_summary = ""
        for m in state.get("messages", []):
            if m.get("role") == AgentRole.REQUIREMENTS:
                requirements_summary = m.get("content", "")
                break

        user_input = state.get("user_input", "")

        return (
            "아래는 사용자의 레고 창작 요구사항과, 레고 관련 참고 지식입니다.\n"
            "이 정보를 기반으로 레고 설계 초안을 작성하세요.\n\n"
            "## 사용자 입력 원문\n"
            f"{user_input}\n\n"
            "## 요구사항 분석 결과\n"
            f"{requirements_summary if requirements_summary else '요구사항 분석 결과가 없습니다.'}\n\n"
            "## 참고 지식 (RAG 검색 결과)\n"
            f"{context if context else '추가 참고 지식이 없습니다.'}"
        )
