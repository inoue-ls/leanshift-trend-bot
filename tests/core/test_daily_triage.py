import json
import pathlib
from datetime import date

from core.daily_triage import (
    Anomaly,
    classify_log,
    find_anomalies,
    format_notification,
    propose_improvements,
    run_triage,
)
from core.run_records import ArticleRunRecord, AttemptRecord, RunRecord

COMPLETED_LOG = "=== [2026-10-04 13:01:31] run_daily.sh 開始 ===\n12/12 件処理成功\n=== [2026-10-04 13:04:14] 完了 ===\n"
STOPPED_LOG = "=== [2026-10-05 10:03:47] run_daily.sh 開始 ===\n"
FAILED_LOG = (
    "=== [2026-10-07 07:00:01] run_daily.sh 開始 ===\nTraceback (most recent call last):\n"
    "=== [2026-10-07 07:00:09] 失敗 (exit 1) ===\n"
)
SKIPPED_LOG = "[SKIP] 本日分は生成済み: outputs/2026-10-04_trends.md\n"


def _article(
    url: str, feedbacks: list[str | None], error: str | None = None
) -> ArticleRunRecord:
    attempts = [
        AttemptRecord(attempt=i, passed=f is None, feedback=f or "") for i, f in enumerate(feedbacks, start=1)
    ]
    return ArticleRunRecord(
        url=url, title="T", source_name="S", attempts=attempts,
        passed=error is None and bool(attempts) and attempts[-1].passed, error=error,
    )


def _run(day: str, articles: list[ArticleRunRecord], fetched: int = 12) -> RunRecord:
    return RunRecord(run_date=day, articles_fetched=fetched, articles=articles)


def _short(n: int) -> str:
    return f"x_post の文字数が範囲外です({n}字、期待値100〜130字)。"


# --- classify_log ---

def test_classify_log() -> None:
    assert classify_log(COMPLETED_LOG) == "completed"
    assert classify_log(STOPPED_LOG) == "stopped"
    assert classify_log(FAILED_LOG) == "failed"
    assert classify_log(SKIPPED_LOG) == "not_started"


# --- find_anomalies ---

def test_healthy_day_has_no_anomaly() -> None:
    run = _run("2026-10-04", [_article(f"u{i}", [None]) for i in range(12)])
    assert find_anomalies({"2026-10-04": COMPLETED_LOG}, {"2026-10-04": run}) == []


def test_stopped_and_failed_runs_are_anomalies() -> None:
    anomalies = find_anomalies({"2026-10-05": STOPPED_LOG, "2026-10-07": FAILED_LOG}, {})

    assert [a.key for a in anomalies] == ["stopped:2026-10-05", "failed:2026-10-07"]


def test_article_errors_short_fetch_and_never_passed_are_anomalies() -> None:
    articles = [_article("a", [], error="RuntimeError: timeout")] + [
        _article(f"u{i}", [_short(80), _short(90), _short(95)]) for i in range(8)
    ]
    run = _run("2026-10-06", articles, fetched=9)

    anomalies = find_anomalies({"2026-10-06": COMPLETED_LOG}, {"2026-10-06": run})

    assert {a.key: a.message for a in anomalies} == {
        "article_errors:2026-10-06": "1 件が例外で分析されなかった（例: RuntimeError: timeout）",
        "fetch_short:2026-10-06": "記事の取得が 9 件だった（想定 12 件）",
        "eval_never_passed:2026-10-06": "8/9 件が評価に一度も合格しないままレポートに載った",
    }


# --- propose_improvements ---

def test_proposals_count_x_post_length_and_title_feedback() -> None:
    articles = [
        _article("a", [_short(80), _short(141), "improved_titleが直訳的です。"]),
        _article("b", [_short(90), None]),
    ]

    proposals = propose_improvements({"2026-10-06": _run("2026-10-06", articles)})

    assert proposals == [
        "X 投稿の文字数で不合格が 3 回（短すぎ 2 回・長すぎ 1 回、平均 104 字、指定 100〜130 字）。"
        "プロンプトの文字数の指示か、範囲そのものを見直す",
        "評価に合格した記事は 1/2 件。生成 → 評価 → 再生成のループで品質が上がっていない。"
        "不合格の理由の多いものから、プロンプトか採点基準を見直す",
        "日本語タイトルが直訳的などの指摘が 1 回。タイトルの法則の例か、採点基準を見直す",
    ]


def test_no_proposals_when_everything_passed() -> None:
    run = _run("2026-10-06", [_article("a", [None])])
    assert propose_improvements({"2026-10-06": run}) == []


# --- format_notification ---

def test_notification_fits_discord_limit() -> None:
    anomalies = [Anomaly(f"k{i}", "2026-10-06", "x" * 100) for i in range(40)]

    message = format_notification("2026-10-06", anomalies, ["p" * 100])

    assert len(message) <= 2000
    assert message.endswith("（続きは STATE.md）")


# --- run_triage ---

def _project(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "logs").mkdir()
    (tmp_path / "runs").mkdir()
    (tmp_path / "logs" / "2026-10-05.log").write_text(STOPPED_LOG, encoding="utf-8")
    (tmp_path / "logs" / "2026-10-06.log").write_text(COMPLETED_LOG, encoding="utf-8")
    run = _run("2026-10-06", [_article(f"u{i}", [_short(80), _short(85), _short(90)]) for i in range(12)])
    (tmp_path / "runs" / "2026-10-06.json").write_text(run.model_dump_json(), encoding="utf-8")
    return tmp_path


def test_run_triage_writes_state_and_notifies_new_anomalies_once(tmp_path: pathlib.Path) -> None:
    root = _project(tmp_path)
    sent: list[str] = []

    run_triage(root, date(2026, 10, 6), sent.append)
    run_triage(root, date(2026, 10, 6), sent.append)

    state = (root / "STATE.md").read_text(encoding="utf-8")
    assert "Last run: 2026-10-06" in state
    assert "2026-10-05: 実行が途中で止まった（ログに完了の行がない）" in state
    assert "2026-10-06: 12/12 件が評価に一度も合格しないままレポートに載った" in state
    assert "X 投稿の文字数で不合格が 36 回" in state
    assert "2026-09-30" in state  # ログのない日は未実行として Watch List に出す
    assert len(sent) == 1
    assert "実行が途中で止まった" in sent[0]
    saved = json.loads((root / "runs" / "triage_notified.json").read_text(encoding="utf-8"))
    assert saved == {"notified": ["eval_never_passed:2026-10-06", "stopped:2026-10-05"]}


def test_run_triage_without_webhook_keeps_anomalies_for_next_time(tmp_path: pathlib.Path) -> None:
    root = _project(tmp_path)
    sent: list[str] = []

    run_triage(root, date(2026, 10, 6), None)
    run_triage(root, date(2026, 10, 6), sent.append)

    assert len(sent) == 1
