import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Mapping, Sequence

from core.github_contributors import API, WEEKLY_TRENDING_URL

DEFAULT_LIMIT = 10


@dataclass(frozen=True)
class Candidate:
    login: str
    handle: str
    repo: str
    followers: int


def collect_ai_trending_candidates(
    get_text: Callable[[str], str], get_json: Callable[[str], Any]
) -> list[Candidate]:
    html = get_text(WEEKLY_TRENDING_URL)
    repos = re.findall(
        r'<article class="Box-row">.*?<h2[^>]*>\s*<a\s[^>]*?href="/([^"]+)"', html, re.S
    )
    seen: set[str] = set()
    candidates: list[Candidate] = []
    for repo in repos:
        topics = get_json(f"{API}/repos/{repo}").get("topics") or []
        if "ai" not in topics and "llm" not in topics:
            continue
        for contributor in get_json(f"{API}/repos/{repo}/contributors")[:3]:
            login = contributor["login"]
            if login in seen:
                continue
            user = get_json(f"{API}/users/{login}")
            handle = user["twitter_username"]
            if handle:
                seen.add(login)
                candidates.append(Candidate(login, handle, repo, user["followers"]))
    return candidates


def iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def select_new_candidates(
    candidates: Sequence[Candidate],
    first_seen: Mapping[str, str],
    week: str,
    limit: int = DEFAULT_LIMIT,
) -> list[Candidate]:
    new = [c for c in candidates if first_seen.get(c.login, week) >= week]
    return sorted(new, key=lambda c: c.followers, reverse=True)[:limit]


def update_weekly_new_x_accounts(
    output_path: str,
    history_path: str,
    get_text: Callable[[str], str],
    get_json: Callable[[str], Any],
    today: date,
    limit: int = DEFAULT_LIMIT,
) -> None:
    try:
        with open(history_path, encoding="utf-8") as f:
            first_seen: dict[str, str] = json.load(f)["first_seen"]
    except FileNotFoundError:
        first_seen = {}
    week = iso_week(today)
    selected = select_new_candidates(
        collect_ai_trending_candidates(get_text, get_json), first_seen, week, limit
    )
    with open(output_path, "w", encoding="utf-8") as f:
        for c in selected:
            f.write(f"- @{c.handle} ({c.login}, {c.repo}) https://x.com/{c.handle}\n")
    for c in selected:
        first_seen.setdefault(c.login, week)
    os.makedirs(os.path.dirname(os.path.abspath(history_path)), exist_ok=True)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump({"first_seen": dict(sorted(first_seen.items()))}, f, indent=2)
        f.write("\n")


def main(
    argv: Sequence[str],
    get_text: Callable[[str], str],
    get_json: Callable[[str], Any],
    today: date,
) -> None:
    parser = argparse.ArgumentParser(
        prog="python3 -m core.weekly_new_x_accounts",
        description="今週の AI 系 trending から、先週までに出ていない人だけを"
        "GitHub のフォロワー数が多い順に書き出し、記録に加える",
    )
    parser.add_argument("output_path", help="一覧を書き出す Markdown ファイル")
    parser.add_argument("history_path", help="login ごとの初出の週を残す JSON ファイル")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="出す人数（既定 10）")
    args = parser.parse_args(argv)
    update_weekly_new_x_accounts(
        args.output_path, args.history_path, get_text, get_json, today, args.limit
    )


if __name__ == "__main__":
    import sys

    from core.github_contributors import _http_get_json, _http_get_text

    main(sys.argv[1:], _http_get_text, _http_get_json, date.today())
