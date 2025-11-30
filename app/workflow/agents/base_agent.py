from abc import ABC, abstractmethod
from typing import Dict, Any, List

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from utils.config import get_llm
from workflow.state import LegoState, AgentRole
from retrieval.vector_store import search_lego_info, format_retrieved_context


class BaseLegoAgent(ABC):
    """공통 로직을 담는 레고 에이전트 베이스 클래스"""

    def __init__(self, role: str, k: int = 4):
        self.role = role
        self.k = k
        self.llm = get_llm()

    # --- 추상 메서드 (각 에이전트에서 구현) ---

    @abstractmethod
    def get_system_prompt(self) -> str:
        ...

    @abstractmethod
    def build_user_message(self, state: LegoState, context: str) -> str:
        ...

    # --- 공통 메인 진입점 ---

    def run(self, state: LegoState) -> LegoState:
        """RAG 검색 → 메시지 구성 → LLM 호출 → 상태 업데이트"""
        messages = state.get("messages", [])

        # 1) RAG 검색
        query = self._build_search_query(state)
        docs = search_lego_info(query=query, k=self.k) if query else []
        context = format_retrieved_context(docs)

        # docs/contexts 저장
        docs_dict = state.get("docs", {})
        docs_dict[self.role] = [d.page_content for d in docs] if docs else []

        ctx_dict = state.get("contexts", {})
        ctx_dict[self.role] = context

        # 2) LLM 메시지 구성
        sys_prompt = self.get_system_prompt()
        user_content = self.build_user_message(state, context)

        llm_messages: List[BaseMessage] = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=user_content),
        ]

        # 3) LLM 호출
        resp = self.llm.invoke(llm_messages)
        answer = resp.content if isinstance(resp, AIMessage) or hasattr(resp, "content") else str(resp)

        # 4) 상태 업데이트 (메시지 로그 추가)
        new_messages = messages.copy()
        new_messages.append(
            {
                "role": self.role,
                "korean_role": AgentRole.to_korean(self.role),
                "content": answer,
            }
        )

        new_state: LegoState = {
            **state,
            "messages": new_messages,
            "docs": docs_dict,
            "contexts": ctx_dict,
        }
        return new_state

    # --- 내부 유틸 ---

    def _build_search_query(self, state: LegoState) -> str:
        """RAG 검색 쿼리 기본 구현 (필요 시 하위 클래스에서 override)"""
        return state.get("user_input", "")
