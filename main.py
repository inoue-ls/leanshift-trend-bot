import pathlib
from datetime import date
from fetcher import (
    fetch_hn_articles,
    fetch_product_hunt_articles,
    fetch_techcrunch_articles,
    fetch_reddit_articles,
)
from analyzer import analyze_articles_batch, _build_client
from models import RawArticle, ProcessedDraft

FETCH_LIMIT = 3
OUTPUTS_DIR = pathlib.Path("outputs")
USER_STATUS_PATH = pathlib.Path("my_status.txt")


def load_user_status() -> str:
    try:
        return USER_STATUS_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def save_markdown_report(
    articles: list[RawArticle],
    drafts: list[ProcessedDraft],
    user_status: str,
) -> str:
    """分析結果を outputs/YYYY-MM-DD_trends.md として保存し、パスを返す"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    output_path = OUTPUTS_DIR / f"{today}_trends.md"

    lines: list[str] = [f"# Trend Report — {today}", ""]

    if user_status:
        lines += ["## ユーザーステータス", "", user_status, "", "---", ""]

    for i, (article, draft) in enumerate(zip(articles, drafts), 1):
        stars = "⭐" * draft.viral_score if draft.viral_score > 0 else "—"
        display_title = draft.improved_title if draft.improved_title else article.title
        lines += [
            f"## 第 {i} 位 — [{article.source_name}] {display_title}",
            "",
            f"- **元記事:** {article.title}",
            f"- **URL:** {article.url}",
            f"- **🔥 バズ度:** {stars} ({draft.viral_score}/5)",
            "",
            "### 一言要約",
            "",
            draft.one_line_summary,
            "",
            "### 背景分析",
            "",
            draft.background_analysis,
            "",
            "### Zenn 記事構成案",
            "",
            draft.zenn_article_structure,
            "",
            "### マネタイズアイデア",
            "",
            draft.monetization_idea,
            "",
            "### 📣 X投稿下書き",
            "",
            "```",
            draft.x_post_draft.replace("{URL}", article.url),
            "```",
            "",
            "---",
            "",
        ]

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)


def main() -> None:
    user_status = load_user_status()

    print("=" * 60)
    print("  leanshift-trend-bot  |  4ソース → 日本語ビジネスアイデア")
    print("=" * 60)

    if user_status:
        print(f"\n[ユーザーステータス] {user_status}")

    print(f"\n[取得 1/4] Hacker News から上位 {FETCH_LIMIT} 件を取得中...")
    hn_articles = fetch_hn_articles(limit=FETCH_LIMIT)
    print(f"      {len(hn_articles)} 件取得完了")

    print(f"\n[取得 2/4] Product Hunt から上位 {FETCH_LIMIT} 件を取得中...")
    ph_articles = fetch_product_hunt_articles(limit=FETCH_LIMIT)
    print(f"      {len(ph_articles)} 件取得完了")

    print(f"\n[取得 3/4] TechCrunch Startups から上位 {FETCH_LIMIT} 件を取得中...")
    tc_articles = fetch_techcrunch_articles(limit=FETCH_LIMIT)
    print(f"      {len(tc_articles)} 件取得完了")

    print(f"\n[取得 4/4] Reddit r/webdev から上位 {FETCH_LIMIT} 件を取得中...")
    reddit_articles = fetch_reddit_articles(limit=FETCH_LIMIT)
    print(f"      {len(reddit_articles)} 件取得完了")

    all_articles = hn_articles + ph_articles + tc_articles + reddit_articles
    print(f"\n合計 {len(all_articles)} 件のデータ取得完了")

    print("\n[分析] Gemini 2.5 Flash Lite で一括バッチ分析中（1回のAPIコール）...")
    client = _build_client()
    drafts = analyze_articles_batch(all_articles, client=client, user_status=user_status)
    print(f"      {len(drafts)} 件の分析完了（関心度順にソート済み）\n")

    # drafts はランク順。対応する RawArticle を article_id で引く
    article_by_id = {a.article_id: a for a in all_articles}

    print("[結果] 分析結果を表示します（関心度順）")
    print("=" * 60)

    for i, draft in enumerate(drafts, 1):
        article = article_by_id[draft.article_id]
        stars = "⭐" * draft.viral_score if draft.viral_score > 0 else "—"
        display_title = draft.improved_title if draft.improved_title else article.title
        print(f"\n【第 {i} 位】{stars} [{article.source_name}] {display_title}")
        print(f"  元記事: {article.title}")
        print(f"  URL: {article.url}")
        print()
        print(f"  ▶ 一言要約\n    {draft.one_line_summary}")
        print()
        print(f"  ▶ 背景分析\n    {draft.background_analysis}")
        print()
        print(f"  ▶ Zenn 記事構成案\n    {draft.zenn_article_structure}")
        print()
        print(f"  ▶ マネタイズアイデア\n    {draft.monetization_idea}")
        print()
        print(f"  ▶ X投稿下書き\n    {draft.x_post_draft.replace('{URL}', article.url)}")
        print("-" * 60)

    ranked_articles = [article_by_id[d.article_id] for d in drafts]
    saved_path = save_markdown_report(ranked_articles, drafts, user_status)
    print(f"\n[保存完了] {saved_path}")


if __name__ == "__main__":
    main()
