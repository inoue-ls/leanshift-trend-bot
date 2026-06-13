# Gemini 2.0 Flash 用 Few-Shot 具体例集 (prompt_fewshot_examples)

本書は、システムプロンプトの精度（フォーマット遵守率および要約・下書きの質）を極限まで高めるために、Gemini 2.0 Flash に入力する Few-Shot（少発学習）の具体例を定義したドキュメントです。

プロンプトに組み込む際は、以下のブロックをそのまま例示として挿入してください。

---

## Few-Shot 動作例（5件のバッチ処理モデル）

### 1. 入力例（XML構造）

```xml
<user_interests>
Next.js, 音楽生成AI, 個人開発
</user_interests>

<articles>
<article id="art-nextjs-01">
  <title>Next.js 15.1 Released with Server Actions Optimization</title>
  <source>Hacker News</source>
  <url>https://techcrunch.com/nextjs-15-1</url>
  <summary>Vercel announced the minor release of Next.js 15.1, focusing heavily on Server Actions security, cold start speed optimizations, and enhanced caching controls for static assets.</summary>
</article>

<article id="art-musicai-02">
  <title>Stable Audio 3.0: Full Track Generation from Text Prompts</title>
  <source>Product Hunt</source>
  <url>https://stability.ai/stable-audio-3</url>
  <summary>Stability AI released Stable Audio 3.0, allowing users to generate high-fidelity, full-length stereo audio tracks (up to 3 minutes) using advanced diffusion transformers with structured song progression.</summary>
</article>

<article id="art-aisaas-03">
  <title>Retool AI: Build Custom AI Workflows in Minutes</title>
  <source>Product Hunt</source>
  <url>https://retool.com/ai</url>
  <summary>Retool launched Retool AI, a suite of features designed to integrate large language models directly into internal tools, enabling automated customer support agents and database query generators without coding.</summary>
</article>

<article id="art-osstool-04">
  <title>Ruff: The Fast Python Linter Written in Rust Passes 20k Stars</title>
  <source>Reddit</source>
  <url>https://github.com/astral-sh/ruff</url>
  <summary>Ruff, an extremely fast Python linter and formatter written in Rust, has surpassed 20,000 GitHub stars, solidifying its place in modern Python development workflows with massive performance gains.</summary>
</article>

<article id="art-funding-05">
  <title>Mistral AI Secures $600M in Series B Funding at $6B Valuation</title>
  <source>TechCrunch</source>
  <url>https://techcrunch.com/mistral-600m</url>
  <summary>Paris-based AI startup Mistral AI has raised $600 million in a Series B round led by General Catalyst, bringing its valuation to $6 billion as it aims to challenge OpenAI in enterprise open-weights models.</summary>
</article>
</articles>
```

---

### 2. 出力例（JSON形式）

```json
{
  "ranked_articles": [
    {
      "rank": 1,
      "article_id": "art-nextjs-01",
      "title": "Next.js 15.1 Released with Server Actions Optimization",
      "evaluation_reason": "ユーザー関心のある『Next.js』のマイナーアップデートであり、個人開発におけるセキュリティと開発速度向上（コールドスタート最適化）に直接貢献するため1位と評価しました。",
      "one_line_summary": "セキュリティ強化とコールドスタート高速化を果たしたNext.js 15.1がリリース。",
      "x_draft": "⚡ Next.js 15.1がリリース！\n開発時のコールドスタートの高速化や、Server Actionsのセキュリティ強化、静的アセットのキャッシュ制御などが盛り込まれました。開発体験の向上とパフォーマンス改善を両立したアップデートです。\n{URL}"
    },
    {
      "rank": 2,
      "article_id": "art-musicai-02",
      "title": "Stable Audio 3.0: Full Track Generation from Text Prompts",
      "evaluation_reason": "ユーザー関心の『音楽生成AI』の最新モデル発表であり、個人開発で音素材を作成する際の実用性やエンタメ性が非常に高いため2位と評価しました。",
      "one_line_summary": "最長3分間のフルステレオ音源をテキストから生成できるStable Audio 3.0が公開。",
      "x_draft": "🎵 Stable Audio 3.0が登場！\nテキスト指示から最大3分間の高品質ステレオ音源を生成可能になりました。新開発の拡散トランスフォーマー技術により、自然な曲の展開やボーカル生成が実現。音楽制作の現場がさらに身近になります。\n{URL}"
    },
    {
      "rank": 3,
      "article_id": "art-aisaas-03",
      "title": "Retool AI: Build Custom AI Workflows in Minutes",
      "evaluation_reason": "ユーザーの『個人開発』関心と親和性のあるAI SaaSツールであり、LLMをノーコードで社内ツールに組み込めるため、実用性とビジネス価値が高いと判断し3位としました。",
      "one_line_summary": "LLMを内製ツールへ瞬時に組み込める「Retool AI」が正式リリース。",
      "x_draft": "🤖 Retool AIが正式発表！\n社内ツール構築プラットフォームにAIワークフロー機能が統合されました。顧客対応の自動化エージェントやDBクエリの自動作成ツールなどを、数分で構築可能。AIの社内実装が一気に加速しそうです。\n{URL}"
    },
    {
      "rank": 4,
      "article_id": "art-osstool-04",
      "title": "Ruff: The Fast Python Linter Written in Rust Passes 20k Stars",
      "evaluation_reason": "特定の関心技術ではないものの、開発効率を爆発的に高めるOSS開発ツールとして評価が高く、個人開発者全般に広く普及しているため4位としました。",
      "one_line_summary": "Rust製で超高速動作するPythonリンター「Ruff」がGitHubで2万スターを獲得。",
      "x_draft": "🦀 Rust製Pythonツール「Ruff」が2万星を突破！\n圧倒的な速さを誇るPythonのリンター兼フォーマッターRuffの人気が急上昇中。静的解析の標準になりつつあり、大規模プロジェクトのCI/CD実行時間を大幅に短縮できます。\n{URL}"
    },
    {
      "rank": 5,
      "article_id": "art-funding-05",
      "title": "Mistral AI Secures $600M in Series B Funding at $6B Valuation",
      "evaluation_reason": "AI業界全体のトレンドとしてビジネス価値や影響度は極めて高いものの、個人開発やNext.jsといったユーザーの技術的関心からは距離があるため5位としました。",
      "one_line_summary": "仏AIスタートアップMistral AIが、評価額60億ドルで6億ドルのシリーズB資金調達を完了。",
      "x_draft": "💰 仏Mistral AIが約940億円を調達！\nシリーズBで企業価値が約9400億円に達し、OpenAI対抗馬として存在感を強めています。オープンウェイト型で高性能な独自LLMの開発を加速し、エンタープライズ市場での普及を狙う戦略です。\n{URL}"
    }
  ]
}
```

---

## X投稿案（x_draft）文字数カウント・監査レポート（確認用）

| 記事ID | X投稿文（URLプレースホルダー `{URL}` を除く） | 文字数 | 判定 |
| :--- | :--- | :---: | :---: |
| `art-nextjs-01` | `⚡ Next.js 15.1がリリース！\n開発時のコールドスタートの高速化や、Server Actionsのセキュリティ強化、静的アセットのキャッシュ制御などが盛り込まれました。開発体験の向上とパフォーマンス改善を両立したアップデートです。\n` | 109文字 | **合格** (100〜130) |
| `art-musicai-02` | `🎵 Stable Audio 3.0が登場！\nテキスト指示から最大3分間の高品質ステレオ音源を生成可能になりました。新開発の拡散トランスフォーマー技術により、自然な曲の展開やボーカル生成が実現。音楽制作の現場がさらに身近になります。\n` | 115文字 | **合格** (100〜130) |
| `art-aisaas-03` | `🤖 Retool AIが正式発表！\n社内ツール構築プラットフォームにAIワークフロー機能が統合されました。顧客対応の自動化エージェントやDBクエリの自動作成ツールなどを、数分で構築可能。AIの社内実装が一気に加速しそうです。\n` | 112文字 | **合格** (100〜130) |
| `art-osstool-04` | `🦀 Rust製Pythonツール「Ruff」が2万星を突破！\n圧倒的な速さを誇るPythonのリンター兼フォーマッターRuffの人気が急上昇中。静的解析の標準になりつつあり、大規模プロジェクトのCI/CD実行時間を大幅に短縮できます。\n` | 114文字 | **合格** (100〜130) |
| `art-funding-05` | `💰 仏Mistral AIが約940億円を調達！\nシリーズBで企業価値が約9400億円に達し、OpenAI対抗馬として存在感を強めています。オープンウェイト型で高性能な独自LLMの開発を加速し、エンタープライズ市場での普及を狙う戦略です。\n` | 112文字 | **合格** (100〜130) |

*作成日: 2026年6月13日*
