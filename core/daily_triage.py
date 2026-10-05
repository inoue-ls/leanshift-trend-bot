"""日次トリアージ(L1: 報告だけ。コードもプロンプトも変えない)。

logs/ と runs/ の直近 7 日分から異常を見つけ、評価フィードバックを集計して改善案を出す。
結果は STATE.md に書き、まだ通知していない異常があるときだけ Discord に送る。
"""
import json
import os
import pathlib
import re
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Mapping

from core.discord_notify import discord_webhook_request
from core.run_records import RunRecord

WINDOW_DAYS = 7
EXPECTED_FETCHED = 12  # 4 ソース × 各 3 件
NEVER_PASSED_RATIO = 0.5
DISCORD_LIMIT = 2000
TRUNCATED_SUFFIX = "…\n（続きは STATE.md）"
NOTIFIED_FILE = "triage_notified.json"

X_POST_LENGTH = re.compile(r"x_post の文字数が範囲外です\((\d+)字、期待値(\d+)〜(\d+)字\)")


@dataclass(frozen=True)
class Anomaly:
    key: str
    day: str
    message: str


def classify_log(text: str) -> str:
    """1 日分のログから実行の結果を判定する"""
    if "完了 ===" in text:
        return "completed"
    if "run_daily.sh 開始" not in text:
        return "not_started"
    if "失敗 (exit" in text or "Traceback" in text:
        return "failed"
    return "stopped"


def find_anomalies(
    logs: Mapping[str, str],
    runs: Mapping[str, RunRecord],
    expected_fetched: int = EXPECTED_FETCHED,
) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    for day in sorted(logs):
        status = classify_log(logs[day])
        if status == "stopped":
            anomalies.append(Anomaly(f"stopped:{day}", day, "実行が途中で止まった（ログに完了の行がない）"))
        elif status == "failed":
            anomalies.append(Anomaly(f"failed:{day}", day, "実行が失敗した（ログに失敗の行か Traceback がある）"))

    for day in sorted(runs):
        run = runs[day]
        errors = [a.error for a in run.articles if a.error]
        if errors:
            anomalies.append(
                Anomaly(f"article_errors:{day}", day, f"{len(errors)} 件が例外で分析されなかった（例: {errors[0]}）")
            )
        if run.articles_fetched < expected_fetched:
            anomalies.append(
                Anomaly(
                    f"fetch_short:{day}", day,
                    f"記事の取得が {run.articles_fetched} 件だった（想定 {expected_fetched} 件）",
                )
            )
        never_passed = [a for a in run.articles if not a.passed and a.error is None]
        if run.articles and len(never_passed) / len(run.articles) >= NEVER_PASSED_RATIO:
            anomalies.append(
                Anomaly(
                    f"eval_never_passed:{day}", day,
                    f"{len(never_passed)}/{len(run.articles)} 件が評価に一度も合格しないままレポートに載った",
                )
            )
    return anomalies


def propose_improvements(runs: Mapping[str, RunRecord]) -> list[str]:
    """不合格の評価フィードバックを集計し、見直す場所の案を出す"""
    articles = [a for run in runs.values() for a in run.articles if a.error is None]
    feedbacks = [t.feedback for a in articles for t in a.attempts if not t.passed]
    proposals: list[str] = []

    lengths = [m for f in feedbacks for m in X_POST_LENGTH.findall(f)]
    if lengths:
        values = [int(n) for n, _, _ in lengths]
        low, high = int(lengths[0][1]), int(lengths[0][2])
        proposals.append(
            f"X 投稿の文字数で不合格が {len(values)} 回"
            f"（短すぎ {sum(v < low for v in values)} 回・長すぎ {sum(v > high for v in values)} 回、"
            f"平均 {round(sum(values) / len(values))} 字、指定 {low}〜{high} 字）。"
            "プロンプトの文字数の指示か、範囲そのものを見直す"
        )

    passed = sum(a.passed for a in articles)
    if articles and passed / len(articles) <= NEVER_PASSED_RATIO:
        proposals.append(
            f"評価に合格した記事は {passed}/{len(articles)} 件。生成 → 評価 → 再生成のループで品質が上がっていない。"
            "不合格の理由の多いものから、プロンプトか採点基準を見直す"
        )

    titles = [f for f in feedbacks if "improved_title" in f]
    if titles:
        proposals.append(f"日本語タイトルが直訳的などの指摘が {len(titles)} 回。タイトルの法則の例か、採点基準を見直す")
    return proposals


def format_notification(today: str, anomalies: list[Anomaly], proposals: list[str]) -> str:
    lines = [f"【日次トリアージ {today}】新しい異常 {len(anomalies)} 件"]
    lines += [f"- {a.day}: {a.message}" for a in anomalies]
    if proposals:
        lines += ["", "改善案:"] + [f"- {p}" for p in proposals]
    message = "\n".join(lines)
    if len(message) > DISCORD_LIMIT:
        message = message[: DISCORD_LIMIT - len(TRUNCATED_SUFFIX)] + TRUNCATED_SUFFIX
    return message


def render_state(today: str, anomalies: list[Anomaly], proposals: list[str], not_run: list[str]) -> str:
    lines = [
        "# Loop State（日次トリアージ）",
        "",
        f"Last run: {today}",
        f"対象: 直近 {WINDOW_DAYS} 日の logs/ と runs/。この STATE.md は毎回作り直す（L1: 報告のみ）",
        "",
        "## High Priority（異常）",
        "",
    ]
    lines += [f"- {a.day}: {a.message}" for a in anomalies] or ["- なし"]
    lines += ["", "## 改善案", ""]
    lines += [f"- {p}" for p in proposals] or ["- なし"]
    lines += ["", "## Watch List", ""]
    lines += [f"- 未実行（ログなし）: {', '.join(not_run)}" if not_run else "- なし"]
    return "\n".join(lines) + "\n"


def run_triage(
    root: pathlib.Path, today: date, send: Callable[[str], None] | None
) -> list[Anomaly]:
    """STATE.md を書き直し、まだ通知していない異常を send で送る。送った異常を返す。
    send が None(Webhook 未設定)のときは送らず、次に送れるときまで未通知のまま残す。"""
    days = [(today - timedelta(days=i)).isoformat() for i in reversed(range(WINDOW_DAYS))]
    logs = {
        d: (root / "logs" / f"{d}.log").read_text(encoding="utf-8")
        for d in days if (root / "logs" / f"{d}.log").exists()
    }
    runs = {
        d: RunRecord.model_validate_json((root / "runs" / f"{d}.json").read_text(encoding="utf-8"))
        for d in days if (root / "runs" / f"{d}.json").exists()
    }
    anomalies = find_anomalies(logs, runs)
    proposals = propose_improvements(runs)
    not_run = [d for d in days if d not in logs]
    (root / "STATE.md").write_text(render_state(today.isoformat(), anomalies, proposals, not_run), encoding="utf-8")

    notified_path = root / "runs" / NOTIFIED_FILE
    notified: set[str] = set()
    if notified_path.exists():
        notified = set(json.loads(notified_path.read_text(encoding="utf-8"))["notified"])
    new = [a for a in anomalies if a.key not in notified]
    if not new or send is None:
        return []
    send(format_notification(today.isoformat(), new, proposals))
    notified_path.parent.mkdir(parents=True, exist_ok=True)
    notified_path.write_text(
        json.dumps({"notified": sorted(notified | {a.key for a in new})}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return new


def _discord_sender(webhook_url: str) -> Callable[[str], None]:
    def send(content: str) -> None:
        with urllib.request.urlopen(discord_webhook_request(webhook_url, content)):
            pass

    return send


if __name__ == "__main__":
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[トリアージ] DISCORD_WEBHOOK_URL が未設定のため、STATE.md の更新だけを行います")
    sent = run_triage(pathlib.Path.cwd(), date.today(), _discord_sender(webhook_url) if webhook_url else None)
    print(f"[トリアージ] STATE.md を更新しました（新しく通知した異常: {len(sent)} 件）")
