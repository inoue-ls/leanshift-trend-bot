import json
import pathlib
from datetime import date

import pytest

import orchestration.langgraph_app.nodes.fetch_nodes as fetch_nodes
import orchestration.langgraph_app.subgraphs.article_analysis as article_analysis
from core.analysis.schemas import ScoredDraft
from core.run_records import AttemptRecord, ArticleRunRecord
from models import AnalysisCore, RawArticle, XDraft, ZennDraft
from orchestration.langgraph_app.graph import build_graph
from orchestration.langgraph_app.state import ArticleState, GraphState, merge_records_by_url
from orchestration.langgraph_app.subgraphs.article_analysis import analyze_article_recorded_node


def _make_article(url: str = "https://example.com/a") -> RawArticle:
    return RawArticle(source_name="S", category="Tech", title="T", url=url, summary="s")


def _make_scored(article: RawArticle) -> ScoredDraft:
    return ScoredDraft(
        raw=article,
        analysis=AnalysisCore(title="T", summary="要約", business_idea="アイデア", viral_score=3, improved_title="改善", rank=0),
        x=XDraft(post="post"),
        zenn=ZennDraft(title="Z", sections=["1"], intro="I", tags=["a", "b", "c"]),
        interest_score=3, business_value_score=3, novelty_score=3,
    )


EvalResult = tuple[bool, str] | Exception


def _state(article: RawArticle) -> ArticleState:
    return {"article": article, "user_status": "", "draft": None, "feedback": None, "iteration": 0}


@pytest.fixture
def gemini(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[EvalResult]]:
    """Gemini の呼び出し(外部 I/O)だけを差し替える。評価結果は記事 URL ごとに順番に返す"""
    script: dict[str, list[EvalResult]] = {}
    monkeypatch.setattr(article_analysis, "build_client", lambda: None)
    monkeypatch.setattr(
        article_analysis, "generate_draft",
        lambda article, client, user_status, feedback: _make_scored(article),
    )

    def evaluate(article: RawArticle, draft: ScoredDraft, client: object) -> tuple[bool, str]:
        result = script[article.url].pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(article_analysis, "evaluate_draft", evaluate)
    return script


def test_recorded_node_keeps_feedback_of_each_attempt(gemini: dict[str, list[EvalResult]]) -> None:
    article = _make_article()
    gemini[article.url] = [(False, "直訳です"), (True, "")]

    result = analyze_article_recorded_node(_state(article))

    assert result["scored"] == [_make_scored(article)]
    assert result["records"] == [
        ArticleRunRecord(
            url=article.url, title="T", source_name="S",
            attempts=[
                AttemptRecord(attempt=1, passed=False, feedback="直訳です"),
                AttemptRecord(attempt=2, passed=True, feedback=""),
            ],
            passed=True, error=None,
        )
    ]


def test_recorded_node_records_exception_and_skips_article(gemini: dict[str, list[EvalResult]]) -> None:
    article = _make_article()
    gemini[article.url] = [(False, "直訳です"), RuntimeError("503 UNAVAILABLE")]

    result = analyze_article_recorded_node(_state(article))

    assert result["scored"] == []
    record = result["records"][0]
    assert record.attempts == [AttemptRecord(attempt=1, passed=False, feedback="直訳です")]
    assert record.error == "RuntimeError: 503 UNAVAILABLE"


def test_merge_records_by_url_replaces_record_of_same_article() -> None:
    old = ArticleRunRecord(url="u", title="T", source_name="S", attempts=[], passed=False, error="x")
    new = ArticleRunRecord(url="u", title="T", source_name="S", attempts=[], passed=True, error=None)

    assert merge_records_by_url([old], [new]) == [new]


def test_graph_saves_run_record_for_every_article(
    gemini: dict[str, list[EvalResult]], monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    ok, broken = _make_article("https://example.com/ok"), _make_article("https://example.com/broken")
    gemini[ok.url] = [(True, "")]
    gemini[broken.url] = [RuntimeError("timeout")]
    monkeypatch.setattr(fetch_nodes, "fetch_hn_articles", lambda limit: [ok, broken])
    for name in ("fetch_product_hunt_articles", "fetch_techcrunch_articles", "fetch_reddit_articles"):
        monkeypatch.setattr(fetch_nodes, name, lambda limit: [])
    monkeypatch.chdir(tmp_path)

    initial: GraphState = {"user_status": "", "articles": [], "scored": [], "ranked": [], "report_path": ""}
    final = build_graph().invoke(initial)

    saved_path = tmp_path / "runs" / f"{date.today().isoformat()}.json"
    assert saved_path.exists()
    assert final["record_path"] == str(pathlib.Path("runs") / f"{date.today().isoformat()}.json")
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    assert saved["articles_fetched"] == 2
    by_url = {a["url"]: a for a in saved["articles"]}
    assert by_url[ok.url]["passed"] is True
    assert by_url[broken.url]["error"] == "RuntimeError: timeout"
