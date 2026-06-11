import json
import os
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types
from models import RawArticle, ProcessedDraft

load_dotenv()

MODEL = "models/gemini-2.5-flash-lite"

_SYSTEM_PROMPT = (
    "あなたは海外テックトレンドを分析する専門家です。\n"
    "与えられた英語記事を分析し、日本のビジネスパーソン向けに以下のJSON形式で回答してください。\n\n"
    "出力は必ず以下のキーを持つ有効なJSONオブジェクトのみとしてください"
    "（説明文・コードブロック記号は不要です）。\n"
    "すべての値は必ずフラットな文字列（string）にしてください。ネストされたオブジェクトや配列は使わないでください。\n"
    "{\n"
    '  "one_line_summary": "何の本質を解決するものか（日本語1文）",\n'
    '  "background_analysis": "なぜ海外で流行しているかの背景（日本語、3〜5文）",\n'
    '  "zenn_article_structure": "Zenn記事のタイトル案と見出し構成を改行区切りで記述した文字列（日本語）",\n'
    '  "monetization_idea": "日本市場向けローカライズビジネスモデル（日本語）"\n'
    "}"
)


def _strip_markdown_fences(text: str) -> str:
    """```json ... ``` などのMarkdownコードブロックを除去する"""
    stripped = text.strip()
    return re.sub(r"^```[a-zA-Z]*\n?(.*?)\n?```$", r"\1", stripped, flags=re.DOTALL)


def _to_str(v: object) -> str:
    """値が文字列でない場合（dict/list等）をJSON文字列に変換する"""
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def parse_ai_response(article_id: str, raw_text: str) -> ProcessedDraft:
    """
    GeminiのレスポンステキストをProcessedDraftにマッピングする。
    Markdownコードブロック付きレスポンスも許容する。
    ※ このロジックはユニットテスト対象。
    """
    clean = _strip_markdown_fences(raw_text)
    data: dict[str, object] = json.loads(clean)

    return ProcessedDraft(
        article_id=article_id,
        one_line_summary=_to_str(data["one_line_summary"]),
        background_analysis=_to_str(data["background_analysis"]),
        zenn_article_structure=_to_str(data["zenn_article_structure"]),
        monetization_idea=_to_str(data["monetization_idea"]),
    )


def _build_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。")
    return genai.Client(api_key=api_key)


def analyze_article(
    article: RawArticle,
    client: genai.Client | None = None,
) -> ProcessedDraft:
    """RawArticle 1件を Gemini に渡し、ProcessedDraft を返す"""
    if client is None:
        client = _build_client()

    user_content = (
        f"Title: {article.title}\n"
        f"URL: {article.url}\n"
        f"Source: {article.source_name} / {article.category}\n\n"
        f"Summary:\n{article.summary}"
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            max_output_tokens=1024,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    raw_text = response.text
    if raw_text is None:
        raise ValueError("Gemini から空のレスポンスが返されました。")
    return parse_ai_response(article.article_id, raw_text)


def analyze_articles(
    articles: list[RawArticle],
    client: genai.Client | None = None,
) -> list[ProcessedDraft]:
    """複数の RawArticle を順次処理して ProcessedDraft のリストを返す"""
    if client is None:
        client = _build_client()
    return [analyze_article(article, client) for article in articles]


if __name__ == "__main__":
    from fetcher import fetch_hn_articles

    articles = fetch_hn_articles(limit=1)
    drafts = analyze_articles(articles)

    for draft in drafts:
        print(json.dumps(draft.model_dump(), ensure_ascii=False, indent=2))
