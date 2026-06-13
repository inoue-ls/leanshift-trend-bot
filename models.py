from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime, timezone


def generate_uuid() -> str:
    return str(uuid4())


def get_utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RawArticle(BaseModel):
    """
    【変更不可】収集した生データのエンティティ
    将来、音楽や投資、Xのデータが増えても必ずこのモデルに適合させる。
    """
    article_id: str = Field(default_factory=generate_uuid, description="UUID v4")
    source_name: str = Field(..., description="例: Hacker News, Product Hunt, Reddit")
    category: str = Field(..., description="例: Tech, Music, Investment")
    title: str = Field(..., description="英語の元タイトル")
    url: str = Field(..., description="ソース元のURL（一意な識別にも使用）")
    summary: str = Field(..., description="ソース元のサマリーまたは本文（英語）")
    collected_at: str = Field(default_factory=get_utc_now_iso, description="収集日時")


class AnalysisCore(BaseModel):
    """Geminiの分析結果（純粋な情報）"""
    title: str
    summary: str
    business_idea: str
    viral_score: int
    improved_title: str
    rank: int


class XDraft(BaseModel):
    """X投稿用の出力"""
    post: str


class ZennDraft(BaseModel):
    """Zenn記事用の出力"""
    title: str
    sections: list[str]
    intro: str
    tags: list[str]


class ProcessedArticle(BaseModel):
    """全出力をまとめる最上位モデル"""
    raw: RawArticle
    analysis: AnalysisCore
    x: XDraft
    zenn: ZennDraft


class ProcessedDraft(BaseModel):
    """
    【後方互換のため残存】ProcessedArticle への移行が完了次第廃止予定。
    """
    draft_id: str = Field(default_factory=generate_uuid, description="UUID v4")
    article_id: str = Field(..., description="紐づくRawArticleのarticle_id（リレーション）")

    one_line_summary: str = Field(..., description="何の本質を解決するものか（日本語1文）")
    background_analysis: str = Field(..., description="なぜ海外で流行しているかの背景（日本語）")
    zenn_article_structure: str = Field(..., description="Zenn記事にする場合のタイトル・構成案（日本語）")
    monetization_idea: str = Field(..., description="日本市場向けローカライズビジネスモデル（日本語）")
    x_post_draft: str = Field(..., description="X（旧Twitter）投稿用下書き（日本語・絵文字フック付き）")
    viral_score: int = Field(default=0, description="1〜5のバズ度スコア（0=バッチ未使用時）")
    improved_title: str = Field(default="", description="バズる法則を適用した日本語タイトル改善案")

    processed_at: str = Field(default_factory=get_utc_now_iso, description="AI処理日時")
