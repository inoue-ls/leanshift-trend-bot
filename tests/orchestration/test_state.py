from orchestration.langgraph_app.state import merge_by_url, merge_by_article_id
from models import RawArticle, AnalysisCore, XDraft, ZennDraft
from core.analysis.schemas import ScoredDraft


def _make_article(url: str) -> RawArticle:
    return RawArticle(source_name="S", category="Tech", title="T", url=url, summary="s")


def _make_scored(url: str) -> ScoredDraft:
    return ScoredDraft(
        raw=_make_article(url),
        analysis=AnalysisCore(title="T", summary="要約", business_idea="アイデア", viral_score=3, improved_title="改善", rank=0),
        x=XDraft(post="post"),
        zenn=ZennDraft(title="Z", sections=["1"], intro="I", tags=["a", "b", "c"]),
        interest_score=3, business_value_score=3, novelty_score=3,
    )


def test_merge_by_url_deduplicates_same_url() -> None:
    a = _make_article("https://example.com/a")
    a_dup = _make_article("https://example.com/a")
    result = merge_by_url([a], [a_dup])
    assert len(result) == 1


def test_merge_by_url_keeps_distinct_urls() -> None:
    a = _make_article("https://example.com/a")
    b = _make_article("https://example.com/b")
    result = merge_by_url([a], [b])
    assert len(result) == 2
    assert {r.url for r in result} == {"https://example.com/a", "https://example.com/b"}


def test_merge_by_url_new_overwrites_existing_for_same_url() -> None:
    a = _make_article("https://example.com/a")
    a_new = RawArticle(source_name="Updated", category="Tech", title="Updated", url="https://example.com/a", summary="s")
    result = merge_by_url([a], [a_new])
    assert len(result) == 1
    assert result[0].source_name == "Updated"


def test_merge_by_article_id_deduplicates_same_article() -> None:
    scored = _make_scored("https://example.com/a")
    # 同じ RawArticle(同一article_id)を含む更新は重複除外される
    result = merge_by_article_id([scored], [scored])
    assert len(result) == 1


def test_merge_by_article_id_keeps_distinct_articles() -> None:
    a = _make_scored("https://example.com/a")
    b = _make_scored("https://example.com/b")
    result = merge_by_article_id([a], [b])
    assert len(result) == 2
