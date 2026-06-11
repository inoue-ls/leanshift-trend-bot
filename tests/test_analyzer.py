import json
import pytest
from analyzer import parse_ai_response, _strip_markdown_fences


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
}


def test_parse_valid_json() -> None:
    draft = parse_ai_response("article-123", json.dumps(VALID_PAYLOAD))
    assert draft.article_id == "article-123"
    assert draft.one_line_summary == VALID_PAYLOAD["one_line_summary"]
    assert draft.background_analysis == VALID_PAYLOAD["background_analysis"]
    assert draft.zenn_article_structure == VALID_PAYLOAD["zenn_article_structure"]
    assert draft.monetization_idea == VALID_PAYLOAD["monetization_idea"]
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
