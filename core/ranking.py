from core.analysis.schemas import ScoredDraft
from models import ProcessedArticle

INTEREST_WEIGHT = 0.5
BUSINESS_VALUE_WEIGHT = 0.3
NOVELTY_WEIGHT = 0.2


def _weighted_score(draft: ScoredDraft) -> float:
    return (
        draft.interest_score * INTEREST_WEIGHT
        + draft.business_value_score * BUSINESS_VALUE_WEIGHT
        + draft.novelty_score * NOVELTY_WEIGHT
    )


def rank_scored_drafts(scored: list[ScoredDraft]) -> list[ProcessedArticle]:
    """軸別スコアの重み付け合計で降順ソートし、rankを確定したProcessedArticleのリストを返す"""
    ordered = sorted(scored, key=_weighted_score, reverse=True)
    ranked: list[ProcessedArticle] = []
    for i, draft in enumerate(ordered, start=1):
        analysis = draft.analysis.model_copy(update={"rank": i})
        ranked.append(ProcessedArticle(raw=draft.raw, analysis=analysis, x=draft.x, zenn=draft.zenn))
    return ranked
