import json
from datetime import date
from pathlib import Path
from typing import Any

from core.weekly_new_x_accounts import (
    Candidate,
    collect_ai_trending_candidates,
    iso_week,
    main,
    select_new_candidates,
    update_weekly_new_x_accounts,
)

# 2026-10-05（月）〜 2026-10-11（日）は ISO 週 2026-W41
TODAY = date(2026, 10, 7)

TRENDING_HTML = (
    '<article class="Box-row"><h2 class="h3">'
    '<a data-hydro-click="{}" href="/acme/llm" class="Link">x</a></h2></article>'
)


def candidate(login: str, followers: int) -> Candidate:
    return Candidate(login=login, handle=f"{login}_x", repo="acme/llm", followers=followers)


def trending_get_text(url: str) -> str:
    return TRENDING_HTML


def trending_get_json(url: str) -> Any:
    """alice（500）、carol（300）、dave（900）が acme/llm の上位3人。"""
    responses: dict[str, Any] = {
        "https://api.github.com/repos/acme/llm": {"topics": ["llm"]},
        "https://api.github.com/repos/acme/llm/contributors": [
            {"login": "alice"},
            {"login": "carol"},
            {"login": "dave"},
        ],
        "https://api.github.com/users/alice": {"twitter_username": "alice_x", "followers": 500},
        "https://api.github.com/users/carol": {"twitter_username": "carol_x", "followers": 300},
        "https://api.github.com/users/dave": {"twitter_username": "dave_x", "followers": 900},
    }
    return responses[url]


def test_iso_week() -> None:
    assert iso_week(TODAY) == "2026-W41"
    assert iso_week(date(2026, 1, 1)) == "2026-W01"
    assert iso_week(date(2027, 1, 1)) == "2026-W53"


def test_select_new_candidates_excludes_recorded_and_sorts_by_followers() -> None:
    candidates = [candidate("alice", 500), candidate("carol", 300), candidate("dave", 900)]
    first_seen = {"alice": "2026-W39", "bob": "2026-W40"}

    result = select_new_candidates(candidates, first_seen, "2026-W41")

    assert [c.login for c in result] == ["dave", "carol"]


def test_select_new_candidates_limits_count() -> None:
    candidates = [candidate(f"u{i}", i) for i in range(12)]

    assert [c.login for c in select_new_candidates(candidates, {}, "2026-W41")] == [
        f"u{i}" for i in range(11, 1, -1)
    ]
    assert [c.login for c in select_new_candidates(candidates, {}, "2026-W41", limit=2)] == [
        "u11",
        "u10",
    ]


def test_select_new_candidates_keeps_people_first_seen_this_week() -> None:
    # 同じ週に実行し直しても、今週初めて出た人は「先週までに出た人」ではないので残る
    candidates = [candidate("alice", 500), candidate("dave", 900)]
    first_seen = {"alice": "2026-W40", "dave": "2026-W41"}

    result = select_new_candidates(candidates, first_seen, "2026-W41")

    assert [c.login for c in result] == ["dave"]


def test_select_new_candidates_keeps_trending_order_on_tie() -> None:
    candidates = [candidate("carol", 300), candidate("alice", 300)]

    result = select_new_candidates(candidates, {}, "2026-W41")

    assert [c.login for c in result] == ["carol", "alice"]


def test_collect_ai_trending_candidates_reads_followers() -> None:
    html = TRENDING_HTML + (
        '<article class="Box-row"><h2 class="h3">'
        '<a href="/beta/web">y</a></h2></article>'
        '<article class="Box-row"><h2 class="h3">'
        '<a href="/gamma/agent">z</a></h2></article>'
    )

    def get_text(url: str) -> str:
        return html

    def get_json(url: str) -> Any:
        responses: dict[str, Any] = {
            "https://api.github.com/repos/acme/llm": {"topics": ["llm"]},
            "https://api.github.com/repos/beta/web": {"topics": ["css"]},
            "https://api.github.com/repos/gamma/agent": {"topics": ["ai"]},
            "https://api.github.com/repos/acme/llm/contributors": [
                {"login": "alice"},
                {"login": "bob"},
                {"login": "carol"},
                {"login": "erin"},
            ],
            "https://api.github.com/repos/gamma/agent/contributors": [
                {"login": "alice"},
                {"login": "dave"},
            ],
            "https://api.github.com/users/alice": {"twitter_username": "alice_x", "followers": 500},
            "https://api.github.com/users/bob": {"twitter_username": None, "followers": 9999},
            "https://api.github.com/users/carol": {"twitter_username": "carol_x", "followers": 300},
            "https://api.github.com/users/dave": {"twitter_username": "dave_x", "followers": 900},
        }
        return responses[url]

    result = collect_ai_trending_candidates(get_text, get_json)

    assert result == [
        Candidate(login="alice", handle="alice_x", repo="acme/llm", followers=500),
        Candidate(login="carol", handle="carol_x", repo="acme/llm", followers=300),
        Candidate(login="dave", handle="dave_x", repo="gamma/agent", followers=900),
    ]


def test_update_weekly_new_x_accounts_writes_list_and_history(tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    history.write_text(
        json.dumps({"first_seen": {"alice": "2026-W39", "bob": "2026-W40"}}), encoding="utf-8"
    )
    output = tmp_path / "x_accounts.md"

    update_weekly_new_x_accounts(
        str(output), str(history), trending_get_text, trending_get_json, TODAY
    )

    assert output.read_text(encoding="utf-8") == (
        "- @dave_x (dave, acme/llm) https://x.com/dave_x\n"
        "- @carol_x (carol, acme/llm) https://x.com/carol_x\n"
    )
    assert json.loads(history.read_text(encoding="utf-8")) == {
        "first_seen": {
            "alice": "2026-W39",
            "bob": "2026-W40",
            "carol": "2026-W41",
            "dave": "2026-W41",
        }
    }


def test_update_weekly_new_x_accounts_starts_without_history(tmp_path: Path) -> None:
    history = tmp_path / "missing" / "history.json"
    output = tmp_path / "x_accounts.md"

    update_weekly_new_x_accounts(
        str(output), str(history), trending_get_text, trending_get_json, TODAY, limit=2
    )

    assert output.read_text(encoding="utf-8") == (
        "- @dave_x (dave, acme/llm) https://x.com/dave_x\n"
        "- @alice_x (alice, acme/llm) https://x.com/alice_x\n"
    )
    assert json.loads(history.read_text(encoding="utf-8")) == {
        "first_seen": {"alice": "2026-W41", "dave": "2026-W41"}
    }


def test_update_weekly_new_x_accounts_same_week_rerun_keeps_list(tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    output = tmp_path / "x_accounts.md"

    for _ in range(2):
        update_weekly_new_x_accounts(
            str(output), str(history), trending_get_text, trending_get_json, TODAY, limit=1
        )

    assert output.read_text(encoding="utf-8") == (
        "- @dave_x (dave, acme/llm) https://x.com/dave_x\n"
    )
    assert json.loads(history.read_text(encoding="utf-8")) == {
        "first_seen": {"dave": "2026-W41"}
    }


def test_main_takes_paths_and_limit(tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    output = tmp_path / "x_accounts.md"

    main(
        [str(output), str(history), "--limit", "1"],
        trending_get_text,
        trending_get_json,
        TODAY,
    )

    assert output.read_text(encoding="utf-8") == (
        "- @dave_x (dave, acme/llm) https://x.com/dave_x\n"
    )
    assert json.loads(history.read_text(encoding="utf-8")) == {
        "first_seen": {"dave": "2026-W41"}
    }
