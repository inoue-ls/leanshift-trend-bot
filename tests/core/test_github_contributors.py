from typing import Any

from core.github_contributors import (
    collect_weekly_trending_x_accounts,
    list_contributor_x_accounts,
    list_weekly_trending_x_accounts,
)


def test_list_weekly_trending_x_accounts_one_line() -> None:
    html = (
        '<article class="Box-row"><h2 class="h3 lh-condensed">'
        '<a href="/acme/llm">acme / llm</a></h2></article>'
        '<article class="Box-row"><h2 class="h3 lh-condensed">'
        '<a href="/other/tool">other / tool</a></h2></article>'
    )
    text_urls: list[str] = []
    json_urls: list[str] = []

    def get_text(url: str) -> str:
        text_urls.append(url)
        return html

    def get_json(url: str) -> Any:
        json_urls.append(url)
        responses: dict[str, Any] = {
            "https://api.github.com/repos/acme/llm/contributors": [{"login": "alice"}],
            "https://api.github.com/users/alice": {
                "login": "alice",
                "twitter_username": "alice_ai",
            },
        }
        return responses[url]

    result = list_weekly_trending_x_accounts(get_text, get_json)

    assert result == "- @alice_ai (alice, acme/llm) https://x.com/alice_ai\n"
    assert text_urls == ["https://github.com/trending?since=weekly"]
    assert not any(
        u.startswith("https://api.github.com/search/repositories") for u in json_urls
    )


def test_list_weekly_trending_x_accounts_skips_contributors_without_x() -> None:
    html = (
        '<article class="Box-row"><h2 class="h3">'
        '<a href="/acme/llm">x</a></h2></article>'
    )

    def get_text(url: str) -> str:
        return html

    def get_json(url: str) -> Any:
        responses: dict[str, Any] = {
            "https://api.github.com/repos/acme/llm/contributors": [
                {"login": "bob"},
                {"login": "carol"},
                {"login": "alice"},
            ],
            "https://api.github.com/users/bob": {"twitter_username": None},
            "https://api.github.com/users/carol": {"twitter_username": ""},
            "https://api.github.com/users/alice": {"twitter_username": "alice_ai"},
        }
        return responses[url]

    result = list_weekly_trending_x_accounts(get_text, get_json)

    assert result == "- @alice_ai (alice, acme/llm) https://x.com/alice_ai\n"
    assert "None" not in result
    assert "bob" not in result
    assert "carol" not in result


def test_list_contributor_x_accounts_one_line() -> None:
    def get_json(url: str) -> Any:
        if url.startswith("https://api.github.com/search/repositories"):
            return {"items": [{"full_name": "acme/llm"}]}
        responses: dict[str, Any] = {
            "https://api.github.com/repos/acme/llm/contributors": [{"login": "alice"}],
            "https://api.github.com/users/alice": {
                "login": "alice",
                "twitter_username": "alice_ai",
            },
        }
        return responses[url]

    result = list_contributor_x_accounts(get_json)

    assert result == "- @alice_ai (alice, acme/llm) https://x.com/alice_ai\n"


def test_collect_weekly_trending_x_accounts_dedupes_across_repos() -> None:
    html = (
        '<article class="Box-row"><h2 class="h3">'
        '<a href="/acme/llm">x</a></h2></article>'
        '<article class="Box-row"><h2 class="h3">'
        '<a href="/beta/agent">y</a></h2></article>'
    )

    def get_text(url: str) -> str:
        return html

    def get_json(url: str) -> Any:
        responses: dict[str, Any] = {
            "https://api.github.com/repos/acme/llm/contributors": [
                {"login": "alice"},
                {"login": "bob"},
            ],
            "https://api.github.com/repos/beta/agent/contributors": [
                {"login": "alice"},
                {"login": "dave"},
                {"login": "erin"},
                {"login": "frank"},
            ],
            "https://api.github.com/users/alice": {"twitter_username": "alice_ai"},
            "https://api.github.com/users/bob": {"twitter_username": "bob_ml"},
            "https://api.github.com/users/dave": {"twitter_username": None},
            "https://api.github.com/users/erin": {"twitter_username": "erin_dev"},
            "https://api.github.com/users/frank": {"twitter_username": "frank_x"},
        }
        return responses[url]

    result = collect_weekly_trending_x_accounts(get_text, get_json)

    assert result == (
        "- @alice_ai (alice, acme/llm) https://x.com/alice_ai\n"
        "- @bob_ml (bob, acme/llm) https://x.com/bob_ml\n"
        "- @erin_dev (erin, beta/agent) https://x.com/erin_dev\n"
    )
