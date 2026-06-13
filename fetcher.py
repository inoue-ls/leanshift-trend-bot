import re
import feedparser
from models import RawArticle

HNRSS_URL = "https://hnrss.org/frontpage?points=200"
PRODUCTHUNT_RSS_URL = "https://www.producthunt.com/feed"
TECHCRUNCH_STARTUPS_RSS_URL = "https://techcrunch.com/category/startups/feed/"
REDDIT_WEBDEV_RSS_URL = "https://www.reddit.com/r/webdev/hot/.rss"
FETCH_LIMIT = 3

_USER_AGENT = "Mozilla/5.0 (compatible; leanshift-trend-bot/1.0)"


def _strip_html(text: str) -> str:
    """HTMLタグを除去してプレーンテキストにする"""
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean).strip()


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


def fetch_product_hunt_articles(limit: int = FETCH_LIMIT) -> list[RawArticle]:
    feed = feedparser.parse(PRODUCTHUNT_RSS_URL)
    articles: list[RawArticle] = []

    for entry in feed.entries[:limit]:
        raw_summary = entry.get("summary", "") or entry.get("description", "")
        articles.append(
            RawArticle(
                source_name="Product Hunt",
                category="Tech",
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                summary=_strip_html(str(raw_summary)),
            )
        )

    return articles


def fetch_techcrunch_articles(limit: int = FETCH_LIMIT) -> list[RawArticle]:
    feed = feedparser.parse(TECHCRUNCH_STARTUPS_RSS_URL)
    articles: list[RawArticle] = []

    for entry in feed.entries[:limit]:
        raw_summary = entry.get("summary", "") or entry.get("description", "")
        articles.append(
            RawArticle(
                source_name="TechCrunch",
                category="Startups",
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                summary=_strip_html(str(raw_summary)),
            )
        )

    return articles


def fetch_reddit_articles(limit: int = FETCH_LIMIT) -> list[RawArticle]:
    feed = feedparser.parse(REDDIT_WEBDEV_RSS_URL, agent=_USER_AGENT)
    articles: list[RawArticle] = []

    for entry in feed.entries[:limit]:
        raw_summary = entry.get("summary", "") or entry.get("description", "")
        articles.append(
            RawArticle(
                source_name="Reddit",
                category="r/webdev",
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                summary=_strip_html(str(raw_summary)),
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
