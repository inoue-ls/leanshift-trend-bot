import logging
from langgraph.graph import StateGraph, START, END
from orchestration.langgraph_app.state import ArticleState
from core.analysis.generate import generate_draft
from core.analysis.evaluate import evaluate_draft
from core.analysis.client import build_client
from core.run_records import build_article_record

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3


def generate_node(state: ArticleState) -> dict:
    client = build_client()
    draft = generate_draft(
        state["article"],
        client=client,
        user_status=state["user_status"],
        feedback=state["feedback"],
    )
    return {"draft": draft}


def evaluate_node(state: ArticleState) -> dict:
    client = build_client()
    draft = state["draft"]
    assert draft is not None
    passed, feedback = evaluate_draft(state["article"], draft, client=client)
    return {
        "feedback": None if passed else feedback,
        "iteration": state["iteration"] + 1,
    }


def route_after_evaluate(state: ArticleState) -> str:
    if state["feedback"] is None or state["iteration"] >= MAX_ITERATIONS:
        return END
    return "generate"


def build_article_analysis_subgraph():
    builder = StateGraph(ArticleState)
    builder.add_node("generate", generate_node)
    builder.add_node("evaluate", evaluate_node)
    builder.add_edge(START, "generate")
    builder.add_edge("generate", "evaluate")
    builder.add_conditional_edges("evaluate", route_after_evaluate)
    return builder.compile()


_SUBGRAPH = build_article_analysis_subgraph()


def analyze_article_node(state: ArticleState) -> dict:
    """記事1件のサブグラフを実行し、親グラフのscoredキーへ結果を返す。
    最終的に失敗した記事はスキップし、パイプライン全体を止めない。"""
    try:
        result = _SUBGRAPH.invoke(state)
    except Exception:
        logger.exception("記事の分析に失敗しました: %s", state["article"].url)
        return {"scored": []}
    return {"scored": [result["draft"]]}


def analyze_article_recorded_node(state: ArticleState) -> dict:
    """analyze_article_node と同じ処理に加え、評価1回ごとのフィードバック・合否・例外を
    親グラフのrecordsキーへ返す。サブグラフの途中経過はstreamで受け取る。"""
    evaluations: list[str | None] = []
    draft = None
    error: Exception | None = None
    try:
        for update in _SUBGRAPH.stream(state, stream_mode="updates"):
            if "generate" in update:
                draft = update["generate"]["draft"]
            if "evaluate" in update:
                evaluations.append(update["evaluate"]["feedback"])
    except Exception as e:
        logger.exception("記事の分析に失敗しました: %s", state["article"].url)
        error = e
    record = build_article_record(state["article"], evaluations, error)
    scored = [] if error is not None or draft is None else [draft]
    return {"scored": scored, "records": [record]}
