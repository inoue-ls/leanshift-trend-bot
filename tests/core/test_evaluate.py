import json
from unittest.mock import MagicMock
from core.analysis.evaluate import (
    run_programmatic_checks,
    build_evaluate_user_content,
    evaluate_draft,
)
from models import RawArticle, AnalysisCore, XDraft, ZennDraft
from core.analysis.schemas import ScoredDraft


def _make_article(**kwargs: str) -> RawArticle:
    defaults: dict[str, str] = {
        "source_name": "Test Source",
        "category": "Tech",
        "title": "Test Title",
        "url": "https://example.com/test",
        "summary": "Test summary text.",
    }
    return RawArticle(**(defaults | kwargs))


def _make_scored_draft(**overrides: object) -> ScoredDraft:
    valid_x_post = "🚀 " + ("あ" * 110) + " {URL}"  # {URL}除いて約112字(100〜130字の範囲内)
    defaults: dict[str, object] = {
        "raw": _make_article(),
        "analysis": AnalysisCore(
            title="Test Title",
            summary="要約",
            business_idea="アイデア",
            viral_score=3,
            improved_title="改善タイトル",
            rank=0,
        ),
        "x": XDraft(post=valid_x_post),
        "zenn": ZennDraft(title="Zennタイトル", sections=["1", "2", "3"], intro="導入文", tags=["A", "B", "C"]),
        "interest_score": 3,
        "business_value_score": 3,
        "novelty_score": 3,
    }
    return ScoredDraft(**(defaults | overrides))  # type: ignore[arg-type]


# --- run_programmatic_checks ---

def test_run_programmatic_checks_passes_valid_draft() -> None:
    draft = _make_scored_draft()
    assert run_programmatic_checks(draft) == []


def test_run_programmatic_checks_flags_short_x_post() -> None:
    draft = _make_scored_draft(x=XDraft(post="短い {URL}"))
    violations = run_programmatic_checks(draft)
    assert any("x_post" in v for v in violations)


def test_run_programmatic_checks_flags_long_x_post() -> None:
    too_long = "🚀 " + ("あ" * 200) + " {URL}"
    draft = _make_scored_draft(x=XDraft(post=too_long))
    violations = run_programmatic_checks(draft)
    assert any("x_post" in v for v in violations)


def test_run_programmatic_checks_flags_invalid_viral_score() -> None:
    draft = _make_scored_draft(
        analysis=AnalysisCore(
            title="Test Title", summary="要約", business_idea="アイデア",
            viral_score=6, improved_title="改善タイトル", rank=0,
        )
    )
    violations = run_programmatic_checks(draft)
    assert any("viral_score" in v for v in violations)


def test_run_programmatic_checks_flags_wrong_tag_count() -> None:
    draft = _make_scored_draft(zenn=ZennDraft(title="T", sections=["1"], intro="I", tags=["A", "B"]))
    violations = run_programmatic_checks(draft)
    assert any("zenn_tags" in v for v in violations)


# --- build_evaluate_user_content ---

def test_build_evaluate_user_content_contains_key_fields() -> None:
    article = _make_article(title="Original")
    draft = _make_scored_draft()
    result = build_evaluate_user_content(article, draft)
    assert "Original" in result
    assert "改善タイトル" in result
    assert "要約" in result


# --- evaluate_draft ---

def test_evaluate_draft_skips_llm_when_programmatic_fails() -> None:
    article = _make_article()
    draft = _make_scored_draft(x=XDraft(post="短い {URL}"))
    mock_client = MagicMock()

    passed, feedback = evaluate_draft(article, draft, client=mock_client)

    mock_client.models.generate_content.assert_not_called()
    assert passed is False
    assert "x_post" in feedback


def test_evaluate_draft_calls_llm_when_programmatic_passes() -> None:
    article = _make_article()
    draft = _make_scored_draft()
    mock_response = MagicMock()
    mock_response.text = json.dumps({"passed": True, "feedback": ""})
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    passed, feedback = evaluate_draft(article, draft, client=mock_client)

    mock_client.models.generate_content.assert_called_once()
    assert passed is True
    assert feedback == ""


def test_evaluate_draft_returns_feedback_on_llm_fail() -> None:
    article = _make_article()
    draft = _make_scored_draft()
    mock_response = MagicMock()
    mock_response.text = json.dumps({"passed": False, "feedback": "improved_titleが直訳的です。"})
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    passed, feedback = evaluate_draft(article, draft, client=mock_client)

    assert passed is False
    assert feedback == "improved_titleが直訳的です。"
