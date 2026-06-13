import json
import pytest
from analyzer import parse_ai_response, _strip_markdown_fences, _build_user_content
from models import RawArticle


# --- テスト用ヘルパー ---

def _make_article(**kwargs: str) -> RawArticle:
    defaults: dict[str, str] = {
        "source_name": "Test Source",
        "category": "Tech",
        "title": "Test Title",
        "url": "https://example.com/test",
        "summary": "Test summary text.",
    }
    return RawArticle(**(defaults | kwargs))


# --- _strip_markdown_fences ---

def test_strip_plain_json_unchanged() -> None:
    raw = '{"key": "value"}'
    assert _strip_markdown_fences(raw) == raw


def test_strip_json_fences() -> None:
    raw = '```json\n{"key": "value"}\n```'
    assert _strip_markdown_fences(raw) == '{"key": "value"}'


def test_strip_generic_fences() -> None:
    raw = '```\n{"key": "value"}\n```'
    assert _strip_markdown_fences(raw) == '{"key": "value"}'


# --- parse_ai_response: 正常系 ---

VALID_PAYLOAD = {
    "one_line_summary": "AIが画像生成の速度を10倍にする手法を提案した。",
    "background_analysis": "海外では生産性ツールへの投資が活発で…",
    "zenn_article_structure": "# タイトル案\n## 1. 背景\n## 2. 技術詳細",
    "monetization_idea": "日本市場向けSaaS展開が有力。",
    "x_post_draft": "🚀 AIが画像生成を10倍高速化！\n新手法により処理時間が劇的に短縮。クリエイター業界に革命をもたらす可能性があります。{URL}",
}


def test_parse_valid_json() -> None:
    draft = parse_ai_response("article-123", json.dumps(VALID_PAYLOAD))
    assert draft.article_id == "article-123"
    assert draft.one_line_summary == VALID_PAYLOAD["one_line_summary"]
    assert draft.background_analysis == VALID_PAYLOAD["background_analysis"]
    assert draft.zenn_article_structure == VALID_PAYLOAD["zenn_article_structure"]
    assert draft.monetization_idea == VALID_PAYLOAD["monetization_idea"]
    assert draft.x_post_draft == VALID_PAYLOAD["x_post_draft"]
    # draft_id と processed_at は自動生成されるため存在チェックのみ
    assert draft.draft_id
    assert draft.processed_at


def test_parse_json_with_markdown_fences() -> None:
    raw = f"```json\n{json.dumps(VALID_PAYLOAD)}\n```"
    draft = parse_ai_response("article-456", raw)
    assert draft.article_id == "article-456"
    assert draft.one_line_summary == VALID_PAYLOAD["one_line_summary"]


# --- parse_ai_response: 異常系 ---

def test_parse_invalid_json_raises() -> None:
    with pytest.raises(json.JSONDecodeError):
        parse_ai_response("x", "not json at all")


def test_parse_missing_key_raises() -> None:
    incomplete = {"one_line_summary": "要約のみ"}  # 3フィールド欠損
    with pytest.raises(KeyError):
        parse_ai_response("x", json.dumps(incomplete))


def test_parse_extra_keys_are_ignored() -> None:
    payload = {**VALID_PAYLOAD, "unexpected_field": "should be ignored"}
    draft = parse_ai_response("article-789", json.dumps(payload))
    assert draft.one_line_summary == VALID_PAYLOAD["one_line_summary"]


# --- _build_user_content ---

def test_build_user_content_with_status_includes_tag() -> None:
    article = _make_article()
    result = _build_user_content(article, "Next.js, 音楽生成AI")
    assert "<user_interests>" in result
    assert "Next.js, 音楽生成AI" in result
    assert "</user_interests>" in result


def test_build_user_content_with_status_interests_before_title() -> None:
    article = _make_article()
    result = _build_user_content(article, "Next.js")
    assert result.index("<user_interests>") < result.index("Title:")


def test_build_user_content_without_status_omits_tag() -> None:
    article = _make_article()
    result = _build_user_content(article, "")
    assert "<user_interests>" not in result
    assert "Title: Test Title" in result


def test_build_user_content_contains_article_fields() -> None:
    article = _make_article(title="My Article", url="https://example.com/a", summary="A summary.")
    result = _build_user_content(article, "")
    assert "Title: My Article" in result
    assert "URL: https://example.com/a" in result
    assert "Summary:\nA summary." in result
