import json
import pytest
from unittest.mock import MagicMock
from analyzer import (
    parse_ai_response,
    _strip_markdown_fences,
    _build_user_content,
    _build_batch_user_content,
    parse_batch_response,
    analyze_articles_batch,
)
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


# --- _build_batch_user_content ---

def test_build_batch_user_content_xml_structure() -> None:
    articles = [
        _make_article(title="Article 1", url="https://a.com"),
        _make_article(title="Article 2", url="https://b.com"),
    ]
    result = _build_batch_user_content(articles, "")
    assert "<articles>" in result
    assert 'id="art-001"' in result
    assert 'id="art-002"' in result
    assert "<title>Article 1</title>" in result
    assert "<title>Article 2</title>" in result
    assert "<url>https://a.com</url>" in result


def test_build_batch_user_content_with_status_before_articles() -> None:
    articles = [_make_article()]
    result = _build_batch_user_content(articles, "Next.js")
    assert "<user_interests>" in result
    assert result.index("<user_interests>") < result.index("<articles>")


def test_build_batch_user_content_no_status_omits_tag() -> None:
    articles = [_make_article()]
    result = _build_batch_user_content(articles, "")
    assert "<user_interests>" not in result
    assert "<articles>" in result


def test_build_batch_user_content_article_fields_in_xml() -> None:
    article = _make_article(
        source_name="Hacker News",
        title="My Title",
        url="https://example.com/x",
        summary="A test summary.",
    )
    result = _build_batch_user_content([article], "")
    assert "<source>Hacker News</source>" in result
    assert "<summary>A test summary.</summary>" in result


# --- parse_batch_response ---

def _make_batch_payload(articles: list[RawArticle], reverse: bool = False) -> str:
    """テスト用バッチレスポンス JSON を生成する（reverse=True で rank が逆順に並ぶ）"""
    items = [
        {
            "rank": i + 1,
            "article_id": f"art-{i+1:03d}",
            "title": article.title,
            "evaluation_reason": f"reason {i+1}",
            "viral_score": (i % 5) + 1,
            "improved_title": f"改善タイトル {i+1}",
            "one_line_summary": f"要約 {i+1}",
            "background_analysis": f"背景 {i+1}",
            "zenn_article_structure": f"構成 {i+1}",
            "monetization_idea": f"マネタイズ {i+1}",
            "x_post_draft": f"🚀 draft {i+1} {{URL}}",
        }
        for i, article in enumerate(articles)
    ]
    if reverse:
        items = list(reversed(items))
    return json.dumps({"ranked_articles": items})


def test_parse_batch_response_maps_article_id() -> None:
    articles = [_make_article(title="A"), _make_article(title="B")]
    id_to_article = {"art-001": articles[0], "art-002": articles[1]}
    drafts = parse_batch_response(_make_batch_payload(articles), id_to_article)
    assert drafts[0].article_id == articles[0].article_id
    assert drafts[1].article_id == articles[1].article_id


def test_parse_batch_response_sorted_by_rank() -> None:
    """Gemini がランク逆順で返してきても正しく昇順ソートされることを確認"""
    articles = [_make_article(title="A"), _make_article(title="B")]
    id_to_article = {"art-001": articles[0], "art-002": articles[1]}
    # reverse=True で rank=2 が先に来る JSON を生成
    drafts = parse_batch_response(_make_batch_payload(articles, reverse=True), id_to_article)
    assert drafts[0].one_line_summary == "要約 1"   # rank 1 が先頭
    assert drafts[1].one_line_summary == "要約 2"


def test_parse_batch_response_all_fields_mapped() -> None:
    articles = [_make_article()]
    id_to_article = {"art-001": articles[0]}
    drafts = parse_batch_response(_make_batch_payload(articles), id_to_article)
    assert drafts[0].one_line_summary == "要約 1"
    assert drafts[0].background_analysis == "背景 1"
    assert drafts[0].zenn_article_structure == "構成 1"
    assert drafts[0].monetization_idea == "マネタイズ 1"
    assert "{URL}" in drafts[0].x_post_draft
    assert drafts[0].viral_score == 1          # (0 % 5) + 1
    assert drafts[0].improved_title == "改善タイトル 1"


def test_parse_batch_response_viral_score_range() -> None:
    """viral_score が 1〜5 の範囲で正しくマッピングされることを確認"""
    articles = [_make_article() for _ in range(5)]
    id_to_article = {f"art-{i+1:03d}": a for i, a in enumerate(articles)}
    drafts = parse_batch_response(_make_batch_payload(articles), id_to_article)
    scores = [d.viral_score for d in drafts]
    assert all(1 <= s <= 5 for s in scores)


# --- analyze_articles_batch（Gemini クライアントをモック）---

def test_analyze_articles_batch_single_api_call() -> None:
    """API が1回だけ呼ばれ、ランク順の ProcessedDraft が返ることを確認"""
    articles = [
        _make_article(title="Article A", url="https://example.com/a"),
        _make_article(title="Article B", url="https://example.com/b"),
    ]
    mock_response = MagicMock()
    mock_response.text = _make_batch_payload(articles)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    drafts = analyze_articles_batch(articles, client=mock_client)

    mock_client.models.generate_content.assert_called_once()
    assert len(drafts) == 2
    assert drafts[0].article_id == articles[0].article_id
    assert drafts[0].one_line_summary == "要約 1"
    assert drafts[1].article_id == articles[1].article_id


def test_analyze_articles_batch_passes_user_status() -> None:
    """user_status が user_content に渡されることを確認（プロンプト内容を検査）"""
    articles = [_make_article()]
    mock_response = MagicMock()
    mock_response.text = _make_batch_payload(articles)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    analyze_articles_batch(articles, client=mock_client, user_status="Next.js, 音楽生成AI")

    call_kwargs = mock_client.models.generate_content.call_args
    contents_arg: str = call_kwargs.kwargs.get("contents") or call_kwargs.args[1]
    assert "Next.js, 音楽生成AI" in contents_arg
    assert "<user_interests>" in contents_arg
