from pydantic import BaseModel
from models import RawArticle, AnalysisCore, XDraft, ZennDraft


class ScoredDraft(BaseModel):
    """1記事分の生成結果 + ランキング用の軸別スコア(models.py外の中間モデル)"""
    raw: RawArticle
    analysis: AnalysisCore
    x: XDraft
    zenn: ZennDraft
    interest_score: int
    business_value_score: int
    novelty_score: int


class GeneratedAnalysisJSON(BaseModel):
    """Geminiの生成ステップ用構造化出力スキーマ"""
    evaluation_reason: str
    interest_score: int
    business_value_score: int
    novelty_score: int
    viral_score: int
    improved_title: str
    summary: str
    business_idea: str
    x_post: str
    zenn_title: str
    zenn_sections: list[str]
    zenn_intro: str
    zenn_tags: list[str]


class EvaluationJSON(BaseModel):
    """Geminiの自己評価ステップ用構造化出力スキーマ"""
    passed: bool
    feedback: str
