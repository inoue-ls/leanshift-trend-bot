from core.ranking import rank_scored_drafts
from models import RawArticle, AnalysisCore, XDraft, ZennDraft
from core.analysis.schemas import ScoredDraft


def _make_scored_draft(
    url: str = "https://example.com/test",
    interest_score: int = 3,
    business_value_score: int = 3,
    novelty_score: int = 3,
) -> ScoredDraft:
    raw = RawArticle(
        source_name="Test Source", category="Tech", title="Test Title", url=url, summary="summary",
    )
    return ScoredDraft(
        raw=raw,
        analysis=AnalysisCore(
            title="Test Title", summary="要約", business_idea="アイデア",
            viral_score=3, improved_title="改善タイトル", rank=0,
        ),
        x=XDraft(post="post {URL}"),
        zenn=ZennDraft(title="T", sections=["1"], intro="I", tags=["A", "B", "C"]),
        interest_score=interest_score,
        business_value_score=business_value_score,
        novelty_score=novelty_score,
    )


def test_rank_scored_drafts_empty_list_returns_empty() -> None:
    assert rank_scored_drafts([]) == []


def test_rank_scored_drafts_higher_weighted_score_ranks_first() -> None:
    # weighted = interest*0.5 + business*0.3 + novelty*0.2
    high = _make_scored_draft(url="https://example.com/high", interest_score=4, business_value_score=2, novelty_score=1)  # 2.8
    low = _make_scored_draft(url="https://example.com/low", interest_score=1, business_value_score=1, novelty_score=1)  # 1.0

    ranked = rank_scored_drafts([low, high])  # 入力順は逆

    assert ranked[0].raw.url == "https://example.com/high"
    assert ranked[1].raw.url == "https://example.com/low"


def test_rank_scored_drafts_assigns_sequential_rank_from_1() -> None:
    drafts = [
        _make_scored_draft(url="https://example.com/a", interest_score=5, business_value_score=5, novelty_score=5),
        _make_scored_draft(url="https://example.com/b", interest_score=1, business_value_score=1, novelty_score=1),
        _make_scored_draft(url="https://example.com/c", interest_score=3, business_value_score=3, novelty_score=3),
    ]

    ranked = rank_scored_drafts(drafts)

    assert [a.analysis.rank for a in ranked] == [1, 2, 3]


def test_rank_scored_drafts_preserves_analysis_content() -> None:
    draft = _make_scored_draft()
    ranked = rank_scored_drafts([draft])
    assert ranked[0].analysis.summary == "要約"
    assert ranked[0].analysis.improved_title == "改善タイトル"
    assert ranked[0].x.post == "post {URL}"
    assert ranked[0].zenn.title == "T"
