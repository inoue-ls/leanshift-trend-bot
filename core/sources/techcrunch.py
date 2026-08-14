import feedparser
from models import RawArticle
from core.sources.base import strip_html

TECHCRUNCH_STARTUPS_RSS_URL = "https://techcrunch.com/category/startups/feed/"
FETCH_LIMIT = 3


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
                summary=strip_html(str(raw_summary)),
            )
        )

    return articles
