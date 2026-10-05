import json
import urllib.request
from datetime import date
from typing import Callable, Mapping

from core.weekly_new_x_accounts import iso_week


def format_weekly_message(list_text: str, week: str) -> str:
    count = len([line for line in list_text.splitlines() if line.strip()])
    if count == 0:
        return f"今週（{week}）の新しい人は0人でした。"
    return f"今週（{week}）の新しい人: {count}人\n{list_text}"


def discord_webhook_request(webhook_url: str, content: str) -> urllib.request.Request:
    return urllib.request.Request(
        webhook_url,
        data=json.dumps({"content": content}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "leanshift-trend-bot"},
        method="POST",
    )


def notify_weekly_list(
    list_path: str,
    environ: Mapping[str, str],
    today: date,
    send: Callable[[urllib.request.Request], None],
) -> None:
    webhook_url = environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("DISCORD_WEBHOOK_URL が設定されていません")
    with open(list_path, encoding="utf-8") as f:
        list_text = f.read()
    send(discord_webhook_request(webhook_url, format_weekly_message(list_text, iso_week(today))))


def _send(request: urllib.request.Request) -> None:
    with urllib.request.urlopen(request):
        pass


if __name__ == "__main__":
    import os
    import sys

    notify_weekly_list(sys.argv[1], os.environ, date.today(), _send)
