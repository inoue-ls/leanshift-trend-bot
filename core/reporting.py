import pathlib
from datetime import date
from models import ProcessedArticle

OUTPUTS_DIR = pathlib.Path("outputs")


def format_console_report(ranked: list[ProcessedArticle], user_status: str) -> str:
    lines: list[str] = ["=" * 60, "  leanshift-trend-bot | LangGraph版", "=" * 60]
    if user_status:
        lines.append(f"\n[ユーザーステータス] {user_status}")

    for article in ranked:
        stars = "⭐" * article.analysis.viral_score if article.analysis.viral_score > 0 else "—"
        lines += [
            f"\n【第 {article.analysis.rank} 位】{stars} [{article.raw.source_name}] {article.analysis.improved_title}",
            f"  元記事: {article.raw.title}",
            f"  URL: {article.raw.url}",
            "",
            f"  ▶ 要約\n    {article.analysis.summary}",
            "",
            f"  ▶ マネタイズアイデア\n    {article.analysis.business_idea}",
            "",
            f"  ▶ X投稿下書き\n    {article.x.post.replace('{URL}', article.raw.url)}",
            "-" * 60,
        ]
    return "\n".join(lines)


def save_markdown_report(ranked: list[ProcessedArticle], user_status: str) -> str:
    """分析結果を outputs/YYYY-MM-DD_trends.md として保存し、パスを返す"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    output_path = OUTPUTS_DIR / f"{today}_trends.md"

    lines: list[str] = [f"# Trend Report — {today}", ""]
    if user_status:
        lines += ["## ユーザーステータス", "", user_status, "", "---", ""]

    for article in ranked:
        stars = "⭐" * article.analysis.viral_score if article.analysis.viral_score > 0 else "—"
        section_list = "\n".join(f"- {s}" for s in article.zenn.sections)
        tag_list = " / ".join(f"`{t}`" for t in article.zenn.tags)
        lines += [
            f"## 第 {article.analysis.rank} 位 — [{article.raw.source_name}] {article.analysis.improved_title}",
            "",
            f"- **元記事:** {article.raw.title}",
            f"- **URL:** {article.raw.url}",
            f"- **🔥 バズ度:** {stars} ({article.analysis.viral_score}/5)",
            "",
            "### 要約",
            "",
            article.analysis.summary,
            "",
            "### 📝 Zenn構成案",
            "",
            f"**タイトル:** {article.zenn.title}",
            "",
            "**見出し構成:**",
            "",
            section_list,
            "",
            "**導入文:**",
            "",
            article.zenn.intro,
            "",
            f"**タグ:** {tag_list}",
            "",
            "### マネタイズアイデア",
            "",
            article.analysis.business_idea,
            "",
            "### 📣 X投稿下書き",
            "",
            "```",
            article.x.post.replace("{URL}", article.raw.url),
            "```",
            "",
            "---",
            "",
        ]

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)
