import re
from typing import Any, Callable

WEEKLY_TRENDING_URL = "https://github.com/trending?since=weekly"

TRENDING_URL = (
    "https://api.github.com/search/repositories"
    "?q=stars:>1000&sort=stars&order=desc&per_page=1"
)
API = "https://api.github.com"


def list_weekly_trending_x_accounts(
    get_text: Callable[[str], str], get_json: Callable[[str], Any]
) -> str:
    html = get_text(WEEKLY_TRENDING_URL)
    match = re.search(
        r'<article class="Box-row">.*?<h2[^>]*>\s*<a href="/([^"]+)"', html, re.S
    )
    if match is None:
        return ""
    repo = match.group(1)
    login = get_json(f"{API}/repos/{repo}/contributors")[0]["login"]
    handle = get_json(f"{API}/users/{login}")["twitter_username"]
    return f"- @{handle} ({login}, {repo}) https://x.com/{handle}\n"


def list_contributor_x_accounts(
    get_json: Callable[[str], Any], trending_url: str = TRENDING_URL
) -> str:
    repo = get_json(trending_url)["items"][0]["full_name"]
    login = get_json(f"{API}/repos/{repo}/contributors")[0]["login"]
    handle = get_json(f"{API}/users/{login}")["twitter_username"]
    return f"- @{handle} ({login}, {repo}) https://x.com/{handle}\n"
