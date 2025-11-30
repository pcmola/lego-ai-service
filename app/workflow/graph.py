from langgraph.graph import StateGraph, END

from workflow.state import LegoState
from workflow.agents.requirements_agent import RequirementsAgent
from workflow.agents.design_agent import DesignAgent
from workflow.agents.refiner_agent import RefinerAgent


def _run_requirements(state: LegoState) -> LegoState:
    agent = RequirementsAgent(k=2)
    return agent.run(state)


def _run_design(state: LegoState) -> LegoState:
    agent = DesignAgent(k=4)
    return agent.run(state)


def _run_refiner(state: LegoState) -> LegoState:
    agent = RefinerAgent(k=2)
    return agent.run(state)


def create_lego_graph() -> StateGraph:
    """레고 창작 Multi-Agent LangGraph 생성"""

    workflow = StateGraph(LegoState)

    workflow.add_node("requirements_agent", _run_requirements)
    workflow.add_node("design_agent", _run_design)
    workflow.add_node("refiner_agent", _run_refiner)

    workflow.set_entry_point("requirements_agent")
    workflow.add_edge("requirements_agent", "design_agent")
    workflow.add_edge("design_agent", "refiner_agent")
    workflow.add_edge("refiner_agent", END)

    return workflow.compile()
