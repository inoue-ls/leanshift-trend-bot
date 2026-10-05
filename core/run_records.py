import pathlib
from typing import Sequence

from pydantic import BaseModel

from models import RawArticle


"""日次実行の記録(記事ごとの試行回数・評価フィードバック・合否・例外)を残す。
あとで実行の記録を分析して、プロンプトや採点基準を直す材料にする。"""


class AttemptRecord(BaseModel):
    attempt: int
    passed: bool
    feedback: str


class ArticleRunRecord(BaseModel):
    url: str
    title: str
    source_name: str
    attempts: list[AttemptRecord]
    passed: bool
    error: str | None


class RunRecord(BaseModel):
    run_date: str
    articles_fetched: int
    articles: list[ArticleRunRecord]


def build_article_record(
    article: RawArticle, evaluations: Sequence[str | None], error: BaseException | None
) -> ArticleRunRecord:
    """evaluations は評価1回ごとのフィードバック(合格なら None)。error は分析を止めた例外"""
    attempts = [
        AttemptRecord(attempt=i, passed=feedback is None, feedback=feedback or "")
        for i, feedback in enumerate(evaluations, start=1)
    ]
    return ArticleRunRecord(
        url=article.url,
        title=article.title,
        source_name=article.source_name,
        attempts=attempts,
        passed=error is None and bool(attempts) and attempts[-1].passed,
        error=None if error is None else f"{type(error).__name__}: {error}",
    )


def save_run_record(record: RunRecord, runs_dir: pathlib.Path) -> str:
    """runs_dir/YYYY-MM-DD.json に保存し、パスを返す"""
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{record.run_date}.json"
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return str(path)
