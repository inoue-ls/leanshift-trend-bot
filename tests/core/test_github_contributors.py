from typing import Any

from core.github_contributors import list_contributor_x_accounts


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
