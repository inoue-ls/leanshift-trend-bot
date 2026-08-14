from core.sources.hackernews import fetch_hn_articles
from core.sources.producthunt import fetch_product_hunt_articles
from core.sources.techcrunch import fetch_techcrunch_articles
from core.sources.reddit import fetch_reddit_articles
from orchestration.langgraph_app.state import GraphState

FETCH_LIMIT = 3


def fetch_hn_node(state: GraphState) -> dict:
    return {"articles": fetch_hn_articles(limit=FETCH_LIMIT)}


def fetch_ph_node(state: GraphState) -> dict:
    return {"articles": fetch_product_hunt_articles(limit=FETCH_LIMIT)}


def fetch_tc_node(state: GraphState) -> dict:
    return {"articles": fetch_techcrunch_articles(limit=FETCH_LIMIT)}


def fetch_reddit_node(state: GraphState) -> dict:
    return {"articles": fetch_reddit_articles(limit=FETCH_LIMIT)}
