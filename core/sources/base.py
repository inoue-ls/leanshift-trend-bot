import re

USER_AGENT = "Mozilla/5.0 (compatible; leanshift-trend-bot/1.0)"


def strip_html(text: str) -> str:
    """HTMLタグを除去してプレーンテキストにする"""
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean).strip()
