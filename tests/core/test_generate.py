import json
from unittest.mock import MagicMock
from core.analysis.generate import build_generate_user_content, generate_draft
from core.analysis.client import MODEL
from models import RawArticle


def _make_article(**kwargs: str) -> RawArticle:
    defaults: dict[str, str] = {
        "source_name": "Test Source",
        "category": "Tech",
        "title": "Test Title",
        "url": "https://example.com/test",
        "summary": "Test summary text.",
    }
    return RawArticle(**(defaults | kwargs))


# --- build_generate_user_content ---

def test_build_generate_user_content_without_status_or_feedback() -> None:
    article = _make_article(title="My Article", url="https://example.com/a", summary="A summary.")
    result = build_generate_user_content(article, "", None)
    assert "<user_interests>" not in result
    assert "<previous_feedback>" not in result
    assert "Title: My Article" in result
    assert "URL: https://example.com/a" in result
    assert "Summary:\nA summary." in result


def test_build_generate_user_content_with_status() -> None:
    article = _make_article()
    result = build_generate_user_content(article, "Next.js, 音楽生成AI", None)
    assert "<user_interests>" in result
    assert "Next.js, 音楽生成AI" in result
    assert result.index("<user_interests>") < result.index("Title:")


def test_build_generate_user_content_with_feedback() -> None:
    article = _make_article()
    result = build_generate_user_content(article, "", "improved_titleが直訳的です。")
    assert "<previous_feedback>" in result
    assert "improved_titleが直訳的です。" in result
    assert result.index("<previous_feedback>") < result.index("Title:")


def test_build_generate_user_content_status_before_feedback() -> None:
    article = _make_article()
    result = build_generate_user_content(article, "Next.js", "フィードバック本文")
    assert result.index("<user_interests>") < result.index("<previous_feedback>")


# --- generate_draft ---

VALID_GENERATION_PAYLOAD = {
    "evaluation_reason": "reason",
    "interest_score": 5,
    "business_value_score": 4,
    "novelty_score": 3,
    "viral_score": 4,
    "improved_title": "改善タイトル",
    "summary": "要約",
    "business_idea": "アイデア",
    "x_post": "🚀 本文 {URL}",
    "zenn_title": "Zennタイトル",
    "zenn_sections": ["1", "2", "3"],
    "zenn_intro": "導入文",
    "zenn_tags": ["A", "B", "C"],
}


def test_generate_draft_calls_api_once_with_correct_model() -> None:
    article = _make_article()
    mock_response = MagicMock()
    mock_response.text = json.dumps(VALID_GENERATION_PAYLOAD)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    generate_draft(article, client=mock_client)

    mock_client.models.generate_content.assert_called_once()
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == MODEL


def test_generate_draft_returns_scored_draft_for_correct_article() -> None:
    article = _make_article(title="Specific Title")
    mock_response = MagicMock()
    mock_response.text = json.dumps(VALID_GENERATION_PAYLOAD)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    draft = generate_draft(article, client=mock_client)

    assert draft.raw.title == "Specific Title"
    assert draft.analysis.summary == "要約"


def test_generate_draft_includes_feedback_in_prompt() -> None:
    article = _make_article()
    mock_response = MagicMock()
    mock_response.text = json.dumps(VALID_GENERATION_PAYLOAD)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    generate_draft(article, client=mock_client, feedback="タイトルを見直してください。")

    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert "タイトルを見直してください。" in call_kwargs["contents"]
