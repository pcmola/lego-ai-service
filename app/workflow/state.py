from typing import Dict, List, TypedDict, Optional


class AgentRole:
    """레고 에이전트 역할 정의"""
    REQUIREMENTS = "REQUIREMENTS"  # 요구사항 분석
    DESIGN = "DESIGN"              # 설계 생성
    REFINER = "REFINER"            # 최종 정리

    @classmethod
    def to_korean(cls, role: str) -> str:
        role_map = {
            cls.REQUIREMENTS: "요구사항 분석",
            cls.DESIGN: "설계 생성",
            cls.REFINER: "최종 정리",
        }
        return role_map.get(role, role)


class LegoState(TypedDict, total=False):
    """LangGraph에서 사용할 상태 정의"""

    # 사용자 입력(사이드바 + 메인 텍스트 통합)
    user_input: str

    # 에이전트별 메시지 기록
    messages: List[Dict]

    # RAG 문서 & 컨텍스트
    docs: Dict[str, List[str]]
    contexts: Dict[str, str]

    # 최종 결과
    final_answer: str

    # 진행 단계
    current_step: str
    prev_node: str
