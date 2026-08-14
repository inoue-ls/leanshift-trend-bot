from langgraph.types import Send
from orchestration.langgraph_app.nodes.dispatch import dispatch_node, dispatch_to_analysis
from orchestration.langgraph_app.state import GraphState
from models import RawArticle


def _make_article(url: str) -> RawArticle:
    return RawArticle(source_name="S", category="Tech", title="T", url=url, summary="s")


def test_dispatch_node_returns_empty_dict() -> None:
    state: GraphState = {"user_status": "", "articles": [], "scored": [], "ranked": [], "report_path": ""}
    assert dispatch_node(state) == {}


def test_dispatch_to_analysis_creates_one_send_per_article() -> None:
    articles = [_make_article("https://a.com"), _make_article("https://b.com")]
    state: GraphState = {"user_status": "Next.js", "articles": articles, "scored": [], "ranked": [], "report_path": ""}

    sends = dispatch_to_analysis(state)

    assert len(sends) == 2
    assert all(isinstance(s, Send) for s in sends)


def test_dispatch_to_analysis_send_targets_analyze_article_node() -> None:
    articles = [_make_article("https://a.com")]
    state: GraphState = {"user_status": "", "articles": articles, "scored": [], "ranked": [], "report_path": ""}

    sends = dispatch_to_analysis(state)

    assert sends[0].node == "analyze_article"


def test_dispatch_to_analysis_payload_initializes_correctly() -> None:
    articles = [_make_article("https://a.com")]
    state: GraphState = {"user_status": "Next.js", "articles": articles, "scored": [], "ranked": [], "report_path": ""}

    sends = dispatch_to_analysis(state)
    payload = sends[0].arg

    assert payload["article"] == articles[0]
    assert payload["user_status"] == "Next.js"
    assert payload["draft"] is None
    assert payload["feedback"] is None
    assert payload["iteration"] == 0
