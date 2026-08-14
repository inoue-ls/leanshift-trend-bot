import feedparser
from models import RawArticle
from core.sources.base import strip_html

PRODUCTHUNT_RSS_URL = "https://www.producthunt.com/feed"
FETCH_LIMIT = 3


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
                summary=strip_html(str(raw_summary)),
            )
        )

    return articles
