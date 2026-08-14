import json
import pytest
from pydantic import ValidationError
from core.analysis.parsing import (
    strip_markdown_fences,
    parse_generation_response,
    parse_evaluation_response,
)
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


# --- strip_markdown_fences ---

def test_strip_plain_json_unchanged() -> None:
    raw = '{"key": "value"}'
    assert strip_markdown_fences(raw) == raw


def test_strip_json_fences() -> None:
    raw = '```json\n{"key": "value"}\n```'
    assert strip_markdown_fences(raw) == '{"key": "value"}'


def test_strip_generic_fences() -> None:
    raw = '```\n{"key": "value"}\n```'
    assert strip_markdown_fences(raw) == '{"key": "value"}'


# --- parse_generation_response ---

VALID_GENERATION_PAYLOAD = {
    "evaluation_reason": "Next.jsに直結する内容のため関連度が高い。",
    "interest_score": 5,
    "business_value_score": 4,
    "novelty_score": 3,
    "viral_score": 4,
    "improved_title": "まだ○○で消耗してる?Next.js新機能まとめ",
    "summary": "Next.jsの新機能によりビルド速度が大幅に改善された。",
    "business_idea": "日本市場向けに導入支援コンサルティングを展開する。",
    "x_post": "🚀 Next.jsの新機能が発表されました。パフォーマンスが大幅に改善され、開発者体験も向上しています。",
    "zenn_title": "Next.js新機能を徹底解説",
    "zenn_sections": ["背景", "技術詳細", "まとめ"],
    "zenn_intro": "Next.jsの新機能について解説します。",
    "zenn_tags": ["Next.js", "React", "TypeScript"],
}


def test_parse_generation_response_valid_maps_all_fields() -> None:
    article = _make_article()
    draft = parse_generation_response(json.dumps(VALID_GENERATION_PAYLOAD), article)

    assert draft.raw == article
    assert draft.analysis.title == article.title
    assert draft.analysis.summary == VALID_GENERATION_PAYLOAD["summary"]
    assert draft.analysis.business_idea == VALID_GENERATION_PAYLOAD["business_idea"]
    assert draft.analysis.viral_score == VALID_GENERATION_PAYLOAD["viral_score"]
    assert draft.analysis.improved_title == VALID_GENERATION_PAYLOAD["improved_title"]
    assert draft.x.post == VALID_GENERATION_PAYLOAD["x_post"]
    assert draft.zenn.title == VALID_GENERATION_PAYLOAD["zenn_title"]
    assert draft.zenn.sections == VALID_GENERATION_PAYLOAD["zenn_sections"]
    assert draft.zenn.intro == VALID_GENERATION_PAYLOAD["zenn_intro"]
    assert draft.zenn.tags == VALID_GENERATION_PAYLOAD["zenn_tags"]
    assert draft.interest_score == 5
    assert draft.business_value_score == 4
    assert draft.novelty_score == 3


def test_parse_generation_response_rank_defaults_to_zero() -> None:
    article = _make_article()
    draft = parse_generation_response(json.dumps(VALID_GENERATION_PAYLOAD), article)
    assert draft.analysis.rank == 0


def test_parse_generation_response_with_markdown_fences() -> None:
    article = _make_article()
    raw = f"```json\n{json.dumps(VALID_GENERATION_PAYLOAD)}\n```"
    draft = parse_generation_response(raw, article)
    assert draft.analysis.summary == VALID_GENERATION_PAYLOAD["summary"]


def test_parse_generation_response_missing_key_raises() -> None:
    incomplete = {"evaluation_reason": "reason only"}
    article = _make_article()
    with pytest.raises(ValidationError):
        parse_generation_response(json.dumps(incomplete), article)


# --- parse_evaluation_response ---

def test_parse_evaluation_response_passed_true() -> None:
    payload = json.dumps({"passed": True, "feedback": ""})
    result = parse_evaluation_response(payload)
    assert result.passed is True
    assert result.feedback == ""


def test_parse_evaluation_response_passed_false_with_feedback() -> None:
    payload = json.dumps({"passed": False, "feedback": "improved_titleが直訳的です。"})
    result = parse_evaluation_response(payload)
    assert result.passed is False
    assert result.feedback == "improved_titleが直訳的です。"
