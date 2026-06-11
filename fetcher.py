import feedparser
from models import RawArticle

HNRSS_URL = "https://hnrss.org/frontpage?points=200"
FETCH_LIMIT = 3


def fetch_hn_articles(limit: int = FETCH_LIMIT) -> list[RawArticle]:
    feed = feedparser.parse(HNRSS_URL)
    articles: list[RawArticle] = []

    for entry in feed.entries[:limit]:
        summary = entry.get("summary", "") or entry.get("description", "")
        articles.append(
            RawArticle(
                source_name="Hacker News",
                category="Tech",
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                summary=summary,
            )
        )

    return articles


if __name__ == "__main__":
    import json

    articles = fetch_hn_articles()
    for i, article in enumerate(articles, 1):
        print(f"--- [{i}] ---")
        print(json.dumps(article.model_dump(), ensure_ascii=False, indent=2))
        print()
