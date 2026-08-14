from google import genai
from google.genai import types
from models import RawArticle
from core.analysis.client import MODEL
from core.analysis.prompts import EVALUATE_SYSTEM_PROMPT
from core.analysis.schemas import ScoredDraft, EvaluationJSON
from core.analysis.parsing import parse_evaluation_response

X_POST_MIN_LENGTH = 100
X_POST_MAX_LENGTH = 130
VIRAL_SCORE_MIN = 1
VIRAL_SCORE_MAX = 5
ZENN_TAGS_COUNT = 3


def run_programmatic_checks(draft: ScoredDraft) -> list[str]:
    """機械的に判定できる品質チェック(LLM呼び出し不要)"""
    violations: list[str] = []

    x_post_length = len(draft.x.post.replace("{URL}", ""))
    if not (X_POST_MIN_LENGTH <= x_post_length <= X_POST_MAX_LENGTH):
        violations.append(
            f"x_post の文字数が範囲外です({x_post_length}字、期待値{X_POST_MIN_LENGTH}〜{X_POST_MAX_LENGTH}字)。"
        )

    if not (VIRAL_SCORE_MIN <= draft.analysis.viral_score <= VIRAL_SCORE_MAX):
        violations.append(
            f"viral_score が範囲外です({draft.analysis.viral_score})。"
            f"{VIRAL_SCORE_MIN}〜{VIRAL_SCORE_MAX}の整数にしてください。"
        )

    if len(draft.zenn.tags) != ZENN_TAGS_COUNT:
        violations.append(f"zenn_tags は{ZENN_TAGS_COUNT}個である必要があります(現在{len(draft.zenn.tags)}個)。")

    return violations


def build_evaluate_user_content(article: RawArticle, draft: ScoredDraft) -> str:
    return (
        f"Original Title: {article.title}\n\n"
        f"improved_title: {draft.analysis.improved_title}\n"
        f"summary: {draft.analysis.summary}\n"
        f"business_idea: {draft.analysis.business_idea}\n"
        f"viral_score: {draft.analysis.viral_score}\n"
        f"x_post: {draft.x.post}\n"
    )


def evaluate_draft(
    article: RawArticle,
    draft: ScoredDraft,
    client: genai.Client,
) -> tuple[bool, str]:
    """機械的チェック→LLM自己評価の順で品質ゲートを判定する"""
    violations = run_programmatic_checks(draft)
    if violations:
        return False, " / ".join(violations)

    user_content = build_evaluate_user_content(article, draft)
    response = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=EVALUATE_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=EvaluationJSON,
            temperature=0.0,
            max_output_tokens=512,
        ),
    )

    raw_text = response.text
    if raw_text is None:
        raise ValueError("Gemini から空のレスポンスが返されました。")
    result = parse_evaluation_response(raw_text)
    return result.passed, result.feedback
