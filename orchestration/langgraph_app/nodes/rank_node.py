from core.ranking import rank_scored_drafts
from orchestration.langgraph_app.state import GraphState


def rank_node(state: GraphState) -> dict:
    ranked = rank_scored_drafts(state["scored"])
    return {"ranked": ranked}
