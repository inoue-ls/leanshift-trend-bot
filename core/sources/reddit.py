import feedparser
from models import RawArticle
from core.sources.base import strip_html, USER_AGENT

REDDIT_WEBDEV_RSS_URL = "https://www.reddit.com/r/webdev/hot/.rss"
FETCH_LIMIT = 3


def fetch_reddit_articles(limit: int = FETCH_LIMIT) -> list[RawArticle]:
    feed = feedparser.parse(REDDIT_WEBDEV_RSS_URL, agent=USER_AGENT)
    articles: list[RawArticle] = []

    for entry in feed.entries[:limit]:
        raw_summary = entry.get("summary", "") or entry.get("description", "")
        articles.append(
            RawArticle(
                source_name="Reddit",
                category="r/webdev",
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                summary=strip_html(str(raw_summary)),
            )
        )

    return articles
