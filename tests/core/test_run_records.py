import json
import pathlib

from core.run_records import (
    ArticleRunRecord,
    AttemptRecord,
    RunRecord,
    build_article_record,
    save_run_record,
)
from models import RawArticle


def _make_article() -> RawArticle:
    return RawArticle(
        source_name="Hacker News", category="Tech", title="T", url="https://example.com/a", summary="s"
    )


def test_passed_on_first_attempt() -> None:
    record = build_article_record(_make_article(), [None], error=None)

    assert record == ArticleRunRecord(
        url="https://example.com/a",
        title="T",
        source_name="Hacker News",
        attempts=[AttemptRecord(attempt=1, passed=True, feedback="")],
        passed=True,
        error=None,
    )


def test_keeps_each_feedback_until_it_passes() -> None:
    record = build_article_record(_make_article(), ["直訳です", "文字数が足りません", None], error=None)

    assert record.attempts == [
        AttemptRecord(attempt=1, passed=False, feedback="直訳です"),
        AttemptRecord(attempt=2, passed=False, feedback="文字数が足りません"),
        AttemptRecord(attempt=3, passed=True, feedback=""),
    ]
    assert record.passed is True


def test_not_passed_when_every_attempt_failed() -> None:
    record = build_article_record(_make_article(), ["a", "b", "c"], error=None)

    assert record.passed is False
    assert record.error is None


def test_exception_is_recorded_with_the_attempts_before_it() -> None:
    record = build_article_record(_make_article(), ["直訳です"], error=RuntimeError("503 UNAVAILABLE"))

    assert record.attempts == [AttemptRecord(attempt=1, passed=False, feedback="直訳です")]
    assert record.passed is False
    assert record.error == "RuntimeError: 503 UNAVAILABLE"


def test_save_run_record_writes_json_named_by_run_date(tmp_path: pathlib.Path) -> None:
    article = build_article_record(_make_article(), [None], error=None)
    run = RunRecord(run_date="2026-10-06", articles_fetched=12, articles=[article])

    path = save_run_record(run, tmp_path / "runs")

    assert path == str(tmp_path / "runs" / "2026-10-06.json")
    saved = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    assert saved["run_date"] == "2026-10-06"
    assert saved["articles_fetched"] == 12
    assert saved["articles"][0]["url"] == "https://example.com/a"
    assert saved["articles"][0]["attempts"] == [{"attempt": 1, "passed": True, "feedback": ""}]
