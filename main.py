from fetcher import fetch_hn_articles
from analyzer import analyze_articles, _build_client

FETCH_LIMIT = 3


def main() -> None:
    print("=" * 60)
    print("  leanshift-trend-bot  |  Hacker News → 日本語ビジネスアイデア")
    print("=" * 60)

    print(f"\n[1/3] Hacker News から上位 {FETCH_LIMIT} 件を取得中...")
    articles = fetch_hn_articles(limit=FETCH_LIMIT)
    print(f"      {len(articles)} 件取得完了\n")

    print("[2/3] Gemini 2.0 Flash で分析中...")
    client = _build_client()
    drafts = analyze_articles(articles, client=client)
    print(f"      {len(drafts)} 件の分析完了\n")

    print("[3/3] 結果を表示します")
    print("=" * 60)

    for i, (article, draft) in enumerate(zip(articles, drafts), 1):
        print(f"\n【記事 {i}】{article.title}")
        print(f"  URL: {article.url}")
        print()
        print(f"  ▶ 一言要約\n    {draft.one_line_summary}")
        print()
        print(f"  ▶ 背景分析\n    {draft.background_analysis}")
        print()
        print(f"  ▶ Zenn 記事構成案\n    {draft.zenn_article_structure}")
        print()
        print(f"  ▶ マネタイズアイデア\n    {draft.monetization_idea}")
        print("-" * 60)


if __name__ == "__main__":
    main()
