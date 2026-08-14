from langgraph.graph import StateGraph, START, END
from orchestration.langgraph_app.state import GraphState
from orchestration.langgraph_app.nodes.fetch_nodes import (
    fetch_hn_node,
    fetch_ph_node,
    fetch_tc_node,
    fetch_reddit_node,
)
from orchestration.langgraph_app.nodes.dispatch import dispatch_node, dispatch_to_analysis
from orchestration.langgraph_app.subgraphs.article_analysis import analyze_article_node
from orchestration.langgraph_app.nodes.rank_node import rank_node
from orchestration.langgraph_app.nodes.report_node import report_node


def build_graph(checkpointer=None):
    builder = StateGraph(GraphState)

    builder.add_node("fetch_hn", fetch_hn_node)
    builder.add_node("fetch_ph", fetch_ph_node)
    builder.add_node("fetch_tc", fetch_tc_node)
    builder.add_node("fetch_reddit", fetch_reddit_node)
    builder.add_node("dispatch", dispatch_node)
    builder.add_node("analyze_article", analyze_article_node)
    builder.add_node("rank", rank_node)
    builder.add_node("report", report_node)

    builder.add_edge(START, "fetch_hn")
    builder.add_edge(START, "fetch_ph")
    builder.add_edge(START, "fetch_tc")
    builder.add_edge(START, "fetch_reddit")
    builder.add_edge("fetch_hn", "dispatch")
    builder.add_edge("fetch_ph", "dispatch")
    builder.add_edge("fetch_tc", "dispatch")
    builder.add_edge("fetch_reddit", "dispatch")
    builder.add_conditional_edges("dispatch", dispatch_to_analysis)
    builder.add_edge("analyze_article", "rank")
    builder.add_edge("rank", "report")
    builder.add_edge("report", END)

    return builder.compile(checkpointer=checkpointer)


graph = build_graph()  # LangGraph Studio用(checkpointer未指定、langgraph devのローカル開発用チェックポインタに委ねる)
