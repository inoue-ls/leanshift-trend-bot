import pytest
from unittest.mock import MagicMock
import orchestration.langgraph_app.subgraphs.article_analysis as article_analysis_module
from orchestration.langgraph_app.subgraphs.article_analysis import (
    route_after_evaluate,
    analyze_article_node,
    MAX_ITERATIONS,
)
from langgraph.graph import END
from models import RawArticle, AnalysisCore, XDraft, ZennDraft
from core.analysis.schemas import ScoredDraft
from orchestration.langgraph_app.state import ArticleState


def _make_article() -> RawArticle:
    return RawArticle(source_name="S", category="Tech", title="T", url="https://example.com/a", summary="s")


def _make_scored() -> ScoredDraft:
    return ScoredDraft(
        raw=_make_article(),
        analysis=AnalysisCore(title="T", summary="要約", business_idea="アイデア", viral_score=3, improved_title="改善", rank=0),
        x=XDraft(post="post"),
        zenn=ZennDraft(title="Z", sections=["1"], intro="I", tags=["a", "b", "c"]),
        interest_score=3, business_value_score=3, novelty_score=3,
    )


# --- route_after_evaluate ---

def test_route_after_evaluate_ends_when_feedback_none() -> None:
    state: ArticleState = {"article": _make_article(), "user_status": "", "draft": None, "feedback": None, "iteration": 1}
    assert route_after_evaluate(state) == END


def test_route_after_evaluate_continues_when_feedback_present_and_under_max() -> None:
    state: ArticleState = {"article": _make_article(), "user_status": "", "draft": None, "feedback": "直してください", "iteration": 1}
    assert route_after_evaluate(state) == "generate"


def test_route_after_evaluate_ends_when_max_iterations_reached_even_with_feedback() -> None:
    state: ArticleState = {"article": _make_article(), "user_status": "", "draft": None, "feedback": "直してください", "iteration": MAX_ITERATIONS}
    assert route_after_evaluate(state) == END


# --- analyze_article_node ---

def test_analyze_article_node_returns_scored_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    scored = _make_scored()
    fake_subgraph = MagicMock()
    fake_subgraph.invoke.return_value = {"draft": scored}
    monkeypatch.setattr(article_analysis_module, "_SUBGRAPH", fake_subgraph)

    state: ArticleState = {"article": _make_article(), "user_status": "", "draft": None, "feedback": None, "iteration": 0}
    result = analyze_article_node(state)

    assert result == {"scored": [scored]}


def test_analyze_article_node_returns_empty_scored_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_subgraph = MagicMock()
    fake_subgraph.invoke.side_effect = RuntimeError("API failure")
    monkeypatch.setattr(article_analysis_module, "_SUBGRAPH", fake_subgraph)

    state: ArticleState = {"article": _make_article(), "user_status": "", "draft": None, "feedback": None, "iteration": 0}
    result = analyze_article_node(state)

    assert result == {"scored": []}
