import json
import os
import re
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types
from models import RawArticle, ProcessedDraft


# ---------------------------------------------------------------------------
# バッチ処理用の中間 Pydantic スキーマ（models.py のマスター定義とは別物）
# Gemini の Structured Outputs 機能に渡すスキーマとして使用する
# ---------------------------------------------------------------------------

class _RankedArticleJSON(BaseModel):
    rank: int
    article_id: str          # XML <article id="art-001"> の値をそのままコピー
    title: str
    evaluation_reason: str
    one_line_summary: str
    background_analysis: str
    zenn_article_structure: str
    monetization_idea: str
    x_post_draft: str


class _BatchAnalysisResponse(BaseModel):
    ranked_articles: list[_RankedArticleJSON]

load_dotenv()

MODEL = "models/gemini-2.5-flash-lite"

_SYSTEM_PROMPT = (
    "あなたは海外テックトレンドを分析する専門家です。\n"
    "与えられた英語記事を分析し、日本のビジネスパーソン向けに以下のJSON形式で回答してください。\n\n"
    "ユーザーの関心事項が `<user_interests>` タグで提供される場合は、"
    "その内容を分析・提案の切り口や優先度に積極的に反映してください。\n\n"
    "出力は必ず以下のキーを持つ有効なJSONオブジェクトのみとしてください"
    "（説明文・コードブロック記号は不要です）。\n"
    "すべての値は必ずフラットな文字列（string）にしてください。ネストされたオブジェクトや配列は使わないでください。\n"
    "{\n"
    '  "one_line_summary": "何の本質を解決するものか（日本語1文）",\n'
    '  "background_analysis": "なぜ海外で流行しているかの背景（日本語、3〜5文）",\n'
    '  "zenn_article_structure": "Zenn記事のタイトル案と見出し構成を改行区切りで記述した文字列（日本語）",\n'
    '  "monetization_idea": "日本市場向けローカライズビジネスモデル（日本語）",\n'
    '  "x_post_draft": "X（旧Twitter）投稿用下書き。'
    "絵文字1個＋改行＋本文1〜2文＋末尾に{URL}プレースホルダー。"
    'URLを除いて100〜130文字。ハッシュタグ不要。"\n'
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
        x_post_draft=_to_str(data["x_post_draft"]),
    )


def _build_user_content(article: RawArticle, user_status: str) -> str:
    """Gemini へ渡す user_content 文字列を組み立てる（テスト対象）"""
    parts: list[str] = []
    if user_status:
        parts.append(f"<user_interests>\n{user_status}\n</user_interests>")
    parts.append(
        f"Title: {article.title}\n"
        f"URL: {article.url}\n"
        f"Source: {article.source_name} / {article.category}\n\n"
        f"Summary:\n{article.summary}"
    )
    return "\n\n".join(parts)


def _build_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。")
    return genai.Client(api_key=api_key)


def analyze_article(
    article: RawArticle,
    client: genai.Client | None = None,
    user_status: str = "",
) -> ProcessedDraft:
    """RawArticle 1件を Gemini に渡し、ProcessedDraft を返す"""
    if client is None:
        client = _build_client()

    user_content = _build_user_content(article, user_status)

    response = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            max_output_tokens=2048,
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
    user_status: str = "",
) -> list[ProcessedDraft]:
    """複数の RawArticle を順次処理して ProcessedDraft のリストを返す"""
    if client is None:
        client = _build_client()
    return [analyze_article(article, client, user_status) for article in articles]


# ---------------------------------------------------------------------------
# バッチ処理システムプロンプト（設計書 ranking_batch_design.md に準拠）
# ---------------------------------------------------------------------------

_BATCH_SYSTEM_PROMPT = (
    "あなたは海外テックトレンドを分析する優秀なリサーチスペシャリストです。\n"
    "与えられた複数の英語技術記事を分析し、ユーザーの関心事項に基づいて順位付けを行い、"
    "各記事の日本語分析データを生成してください。\n\n"
    "# 処理ルール\n"
    "1. `<articles>` 内の全記事を漏れなく評価すること。一部を省略することは認めない。\n"
    "2. 以下の基準で各記事をスコアリングし、総合順位を決定する。\n"
    "   - ユーザー関心度（比重 50%）: `<user_interests>` に合致しているか\n"
    "   - ビジネス・技術価値（比重 30%）: 日本の開発者・ビジネスパーソンに実用的か\n"
    "   - 新規性（比重 20%）: 新概念や新製品の発表か\n"
    "3. `article_id` には入力 `<article id=\"...\">` の値を正確にコピーすること。\n"
    "4. `rank` は 1（最高）から始まる重複のない連番とし、出力配列は rank 昇順でソートすること。\n\n"
    "# x_post_draft のルール\n"
    "絵文字1個＋改行＋本文1〜2文＋末尾に {URL} プレースホルダーを含める。"
    "URL を除いて 100〜130 文字。ハッシュタグ不要。\n"
)


def _build_batch_user_content(articles: list[RawArticle], user_status: str) -> str:
    """バッチ処理用の user_content（XMLタグ束ね形式）を組み立てる（テスト対象）"""
    parts: list[str] = []
    if user_status:
        parts.append(f"<user_interests>\n{user_status}\n</user_interests>")

    xml_articles: list[str] = []
    for i, article in enumerate(articles, 1):
        xml_id = f"art-{i:03d}"
        xml_articles.append(
            f'<article id="{xml_id}">\n'
            f"  <title>{article.title}</title>\n"
            f"  <source>{article.source_name}</source>\n"
            f"  <url>{article.url}</url>\n"
            f"  <summary>{article.summary}</summary>\n"
            f"</article>"
        )
    parts.append("<articles>\n" + "\n\n".join(xml_articles) + "\n</articles>")
    return "\n\n".join(parts)


def _build_id_map(articles: list[RawArticle]) -> dict[str, RawArticle]:
    """XML ID（art-001 等）→ RawArticle の対応辞書を生成する"""
    return {f"art-{i:03d}": article for i, article in enumerate(articles, 1)}


def parse_batch_response(
    raw_text: str,
    id_to_article: dict[str, RawArticle],
) -> list[ProcessedDraft]:
    """Gemini バッチレスポンスを rank 昇順の ProcessedDraft リストに変換する（テスト対象）"""
    clean = _strip_markdown_fences(raw_text)
    batch = _BatchAnalysisResponse.model_validate_json(clean)

    drafts: list[ProcessedDraft] = []
    for item in sorted(batch.ranked_articles, key=lambda x: x.rank):
        article = id_to_article[item.article_id]
        drafts.append(
            ProcessedDraft(
                article_id=article.article_id,
                one_line_summary=item.one_line_summary,
                background_analysis=item.background_analysis,
                zenn_article_structure=item.zenn_article_structure,
                monetization_idea=item.monetization_idea,
                x_post_draft=item.x_post_draft,
            )
        )
    return drafts


def analyze_articles_batch(
    articles: list[RawArticle],
    client: genai.Client | None = None,
    user_status: str = "",
) -> list[ProcessedDraft]:
    """全記事を1回の Gemini APIコールで一括分析し、関心度順の ProcessedDraft リストを返す"""
    if client is None:
        client = _build_client()

    id_to_article = _build_id_map(articles)
    user_content = _build_batch_user_content(articles, user_status)

    response = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=_BATCH_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=_BatchAnalysisResponse,
            temperature=0.2,
            max_output_tokens=8192,
        ),
    )

    raw_text = response.text
    if raw_text is None:
        raise ValueError("Gemini から空のレスポンスが返されました。")
    return parse_batch_response(raw_text, id_to_article)


if __name__ == "__main__":
    from fetcher import fetch_hn_articles

    articles = fetch_hn_articles(limit=1)
    drafts = analyze_articles(articles)

    for draft in drafts:
        print(json.dumps(draft.model_dump(), ensure_ascii=False, indent=2))
