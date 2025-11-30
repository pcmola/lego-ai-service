from typing import Dict, Any

from workflow.agents.base_agent import BaseLegoAgent
from workflow.state import LegoState, AgentRole
from utils.prompt import REQUIREMENTS_ANALYZER_PROMPT


class RequirementsAgent(BaseLegoAgent):
    """레고 요구사항 분석 에이전트"""

    def __init__(self, k: int = 2):
        super().__init__(role=AgentRole.REQUIREMENTS, k=k)

    def get_system_prompt(self) -> str:
        return REQUIREMENTS_ANALYZER_PROMPT

    def build_user_message(self, state: LegoState, context: str) -> str:
        user_input = state.get("user_input", "")
        return (
            "다음은 사용자가 입력한 레고 창작 아이디어와 제약 조건입니다.\n"
            "이를 읽고 요구사항을 구조화하여 정리하세요.\n\n"
            f"## 사용자 입력\n{user_input}\n\n"
            "## 참고용 레고 설계 지식 (있다면)\n"
            f"{context if context else '추가 지식이 없습니다.'}"
        )
