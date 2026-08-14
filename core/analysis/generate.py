from google import genai
from google.genai import types
from models import RawArticle
from core.analysis.client import MODEL
from core.analysis.prompts import GENERATE_SYSTEM_PROMPT
from core.analysis.schemas import ScoredDraft, GeneratedAnalysisJSON
from core.analysis.parsing import parse_generation_response


def build_generate_user_content(article: RawArticle, user_status: str, feedback: str | None) -> str:
    """Gemini生成ステップへ渡すuser_content文字列を組み立てる"""
    parts: list[str] = []
    if user_status:
        parts.append(f"<user_interests>\n{user_status}\n</user_interests>")
    if feedback:
        parts.append(f"<previous_feedback>\n{feedback}\n</previous_feedback>")
    parts.append(
        f"Title: {article.title}\n"
        f"URL: {article.url}\n"
        f"Source: {article.source_name} / {article.category}\n\n"
        f"Summary:\n{article.summary}"
    )
    return "\n\n".join(parts)


def generate_draft(
    article: RawArticle,
    client: genai.Client,
    user_status: str = "",
    feedback: str | None = None,
) -> ScoredDraft:
    """RawArticle 1件をGeminiに渡し、ScoredDraftを返す"""
    user_content = build_generate_user_content(article, user_status, feedback)

    response = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=GENERATE_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=GeneratedAnalysisJSON,
            temperature=0.2,
            max_output_tokens=4096,
        ),
    )

    raw_text = response.text
    if raw_text is None:
        raise ValueError("Gemini から空のレスポンスが返されました。")
    return parse_generation_response(raw_text, article)
