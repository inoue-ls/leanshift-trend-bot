from typing import Annotated, TypedDict
from models import RawArticle, ProcessedArticle
from core.analysis.schemas import ScoredDraft


def merge_by_url(existing: list[RawArticle], new: list[RawArticle]) -> list[RawArticle]:
    """URLをキーに重複を排除しながらマージする(再実行・リトライ時の重複追加を防止)"""
    by_url = {a.url: a for a in existing}
    for a in new:
        by_url[a.url] = a
    return list(by_url.values())


def merge_by_article_id(existing: list[ScoredDraft], new: list[ScoredDraft]) -> list[ScoredDraft]:
    """article_idをキーに重複を排除しながらマージする(再実行・リトライ時の重複追加を防止)"""
    by_id = {d.raw.article_id: d for d in existing}
    for d in new:
        by_id[d.raw.article_id] = d
    return list(by_id.values())


class GraphState(TypedDict):
    user_status: str
    articles: Annotated[list[RawArticle], merge_by_url]
    scored: Annotated[list[ScoredDraft], merge_by_article_id]
    ranked: list[ProcessedArticle]
    report_path: str


class ArticleState(TypedDict):
    article: RawArticle
    user_status: str
    draft: ScoredDraft | None
    feedback: str | None
    iteration: int
