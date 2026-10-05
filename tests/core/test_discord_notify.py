import json
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from core.discord_notify import (
    discord_webhook_request,
    format_weekly_message,
    notify_weekly_list,
)

# 2026-10-05（月）は ISO 週 2026-W41
MONDAY = date(2026, 10, 5)
WEBHOOK = "https://discord.com/api/webhooks/123/abc"
LIST_TEXT = (
    "- @dave_x (dave, acme/llm) https://x.com/dave_x\n"
    "- @carol_x (carol, acme/llm) https://x.com/carol_x\n"
)


def body(request: urllib.request.Request) -> Any:
    assert isinstance(request.data, bytes)
    return json.loads(request.data.decode("utf-8"))


def test_format_weekly_message_lists_people() -> None:
    assert format_weekly_message(LIST_TEXT, "2026-W41") == (
        "今週（2026-W41）の新しい人: 2人\n" + LIST_TEXT
    )


def test_format_weekly_message_zero_people() -> None:
    assert format_weekly_message("", "2026-W41") == "今週（2026-W41）の新しい人は0人でした。"


def test_discord_webhook_request() -> None:
    request = discord_webhook_request(WEBHOOK, "hello")

    assert request.full_url == WEBHOOK
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json"
    # Discord は urllib の既定の User-Agent を拒むため、独自の値を付ける
    assert request.get_header("User-agent") == "leanshift-trend-bot"
    assert body(request) == {"content": "hello"}


def test_notify_weekly_list_sends_list(tmp_path: Path) -> None:
    path = tmp_path / "x_accounts.md"
    path.write_text(LIST_TEXT, encoding="utf-8")
    sent: list[urllib.request.Request] = []

    notify_weekly_list(str(path), {"DISCORD_WEBHOOK_URL": WEBHOOK}, MONDAY, sent.append)

    assert len(sent) == 1
    assert sent[0].full_url == WEBHOOK
    assert body(sent[0]) == {
        "content": "今週（2026-W41）の新しい人: 2人\n" + LIST_TEXT
    }


def test_notify_weekly_list_sends_zero_people(tmp_path: Path) -> None:
    path = tmp_path / "x_accounts.md"
    path.write_text("", encoding="utf-8")
    sent: list[urllib.request.Request] = []

    notify_weekly_list(str(path), {"DISCORD_WEBHOOK_URL": WEBHOOK}, MONDAY, sent.append)

    assert len(sent) == 1
    assert body(sent[0]) == {
        "content": "今週（2026-W41）の新しい人は0人でした。"
    }


def test_notify_weekly_list_requires_webhook_url(tmp_path: Path) -> None:
    path = tmp_path / "x_accounts.md"
    path.write_text(LIST_TEXT, encoding="utf-8")
    sent: list[urllib.request.Request] = []

    with pytest.raises(RuntimeError, match="DISCORD_WEBHOOK_URL"):
        notify_weekly_list(str(path), {"DISCORD_WEBHOOK_URL": ""}, MONDAY, sent.append)

    assert sent == []
