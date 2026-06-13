from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime, timezone  # timezone を追加

def generate_uuid() -> str:
    return str(uuid4())

def get_utc_now_iso() -> str:
    # 2026年現在の非推奨警告を回避する、もっとも安全なUTC取得方法
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
    # default_factory を安全な関数に変更
    collected_at: str = Field(default_factory=get_utc_now_iso, description="収集日時")

class ZennDraft(BaseModel):
    """Zenn 記事構成案エンティティ（バッチ分析で生成）"""
    zenn_draft_id: str = Field(default_factory=generate_uuid, description="UUID v4")
    article_id: str = Field(..., description="紐づくRawArticleのarticle_id")
    zenn_title: str = Field(..., description="Zenn向け日本語タイトル")
    zenn_sections: list[str] = Field(..., description="H2見出し候補 3〜5個")
    zenn_intro: str = Field(..., description="導入文 200字程度")
    zenn_tags: list[str] = Field(..., description="Zennのタグ候補 3個")
    created_at: str = Field(default_factory=get_utc_now_iso, description="生成日時")


class ProcessedDraft(BaseModel):
    """
    【変更不可】AIが処理した後の下書き・考察エンティティ
    Obsidianへの出力や、将来のDB保存、OpenClaw連携でもこのデータ構造をマスターとする。
    """
    draft_id: str = Field(default_factory=generate_uuid, description="UUID v4")
    article_id: str = Field(..., description="紐づくRawArticleのarticle_id（リレーション）")
    
    # AIが生成する構造化データ
    one_line_summary: str = Field(..., description="何の本質を解決するものか（日本語1文）")
    background_analysis: str = Field(..., description="なぜ海外で流行しているかの背景（日本語）")
    zenn_article_structure: str = Field(..., description="Zenn記事にする場合のタイトル・構成案（日本語）")
    monetization_idea: str = Field(..., description="日本市場向けローカライズビジネスモデル（日本語）")
    x_post_draft: str = Field(..., description="X（旧Twitter）投稿用下書き（日本語・絵文字フック付き）")
    # バッチ分析で追加されるバズ指標（単記事パスとの後方互換のためデフォルト値あり）
    viral_score: int = Field(default=0, description="1〜5のバズ度スコア（0=バッチ未使用時）")
    improved_title: str = Field(default="", description="バズる法則を適用した日本語タイトル改善案")

    # default_factory を安全な関数に変更
    processed_at: str = Field(default_factory=get_utc_now_iso, description="AI処理日時")
