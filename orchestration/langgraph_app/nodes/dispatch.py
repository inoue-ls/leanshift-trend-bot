from langgraph.types import Send
from orchestration.langgraph_app.state import GraphState, ArticleState


def dispatch_node(state: GraphState) -> dict:
    """Send APIによるfan-outの起点となるno-opノード(条件付きエッジはノードからしか発行できないため必要)"""
    return {}


def dispatch_to_analysis(state: GraphState) -> list[Send]:
    return [
        Send(
            "analyze_article",
            ArticleState(
                article=article,
                user_status=state["user_status"],
                draft=None,
                feedback=None,
                iteration=0,
            ),
        )
        for article in state["articles"]
    ]
