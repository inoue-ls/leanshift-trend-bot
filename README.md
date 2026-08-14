# leanshift-trend-bot

海外テックフィードの最新トレンド記事を **LangGraph + Gemini 2.5 Flash Lite** で自動分析・順位付けし、日本語の起業アイデア、Zenn用ブログ構成、およびX（旧Twitter）投稿用下書きを自動生成するキュレーションシステムです。

記事ごとにSend APIで並列fan-outし、各記事は「生成 → 自己評価 → 改善」のループ（最大3回）を経て品質を担保します。チェックポイント（AsyncSqliteSaver）による再開性、LangGraph Studioでのグラフ可視化にも対応しています。

---

## 🚀 主要機能

1.  **4つの主要テックソースからの並列自動収集**
    *   Hacker News (points>=200)、Product Hunt、TechCrunch Startups、Reddit r/webdev からそれぞれ3件、計12件の記事をLangGraphの並列ノードで自動取得。
2.  **HTMLクレンジングによる不要ノイズ除去**
    *   RSSのサマリーに含まれる不要なHTMLタグを自動的にクレンジングし、APIトークン消費量を節約。
3.  **ユーザーステータス（my_status.txt）連携**
    *   `my_status.txt` に書かれた「今週の関心」を自動で読み込み、AI解析の切り口や優先順位をパーソナライズ。
4.  **記事ごとのSend API fan-out分析＋自己評価ループ**
    *   12記事をSend APIで並列に個別分析。各記事は生成 → 機械的チェック＋LLM自己評価 → 不合格ならフィードバック付きで再生成、というループを最大3回実行してから確定。fan-in後は関心度・ビジネス価値・新規性の重み付けスコアで機械的にランキング。
5.  **バズ度評価（1〜5）と日本語タイトル改善**
    *   日本のテックコミュニティ（X、Zenn、はてブ）での拡散力を5段階でスコアリング。「バズるタイトルの法則」に則った日本語タイトル改善案を提案。
6.  **URL対応のX（旧Twitter）投稿下書き自動生成**
    *   元のURLプレースホルダーを末尾に含め、絵文字フックを用いた100〜130文字（日本語）のSNSドラフトを自動生成。
7.  **Zenn記事構成案の作成**
    *   ブログ記事の仮タイトル、見出し構成（H2以下）、キャッチーな導入文、および関連タグを自動生成。
8.  **チェックポイントによる再開性**
    *   `AsyncSqliteSaver`（WALモード）で実行状態を永続化。同日中の再実行は途中から再開可能。
9.  **LangGraph Studio対応**
    *   `langgraph.json` を同梱。`langgraph dev` でグラフ構造を可視化・デバッグできる。

---

## 🏗️ アーキテクチャ

将来LangGraphから他フレームワークへ移行することも見据え、ports-and-adapters構成を採用しています。

- **`core/`** — フレームワーク非依存のドメインロジック（RSS取得・プロンプト構築・パース・自己評価・ランキング・レポート生成）。LangGraphに依存しない。
- **`orchestration/langgraph_app/`** — LangGraph固有のグラフ・ノード・State・checkpointer実装。`core/` の関数を呼び出すだけの薄いアダプタ層。

```
START → 4ソース並列fetch → dispatch(Send API fan-out) → 記事ごとに
  [generate → evaluate → (不合格なら再生成 / 合格ならEND)]
→ fan-in → 重み付けランキング → レポート保存 → END
```

詳細な設計は [`docs/superpowers/specs/2026-08-14-langgraph-migration-design.md`](docs/superpowers/specs/2026-08-14-langgraph-migration-design.md) を参照してください。

---

## 💻 デモ出力（コンソール）

```text
[実行開始] LangGraphパイプラインを起動します...
============================================================
  leanshift-trend-bot | LangGraph版
============================================================

[ユーザーステータス] 今週の関心: Next.js, 音楽生成AI

【第 1 位】⭐⭐⭐⭐ [Hacker News] AIの未来はOSSにあり？
  元記事: Open source AI must win
  URL: https://opensourceaimustwin.com/?share=v2

  ▶ 要約
    オープンソースAIの重要性と、それが業界をリードすべき理由を論じる記事。透明性やカスタマイズ性の観点から、
    海外テックコミュニティで活発に議論されています。

  ▶ マネタイズアイデア
    オープンソースAIモデルの商用利用ライセンス販売、または関連する構築・運用コンサルティング。

  ▶ X投稿下書き
    🎨 オープンソースAIの重要性を説く記事を発見しました！
    透明性、カスタマイズ性、コミュニティ主導のイノベーションが鍵。音楽生成AIの未来にも期待が高まりますね。
    https://opensourceaimustwin.com/?share=v2
------------------------------------------------------------
...

12/12 件処理成功

[保存完了] outputs/2026-08-14_trends.md
```

---

## 🛠️ セットアップと実行手順

### 1. 依存関係のインストール

```bash
git clone https://github.com/inoue-ls/leanshift-trend-bot.git
cd leanshift-trend-bot
pip install -r requirements.txt
```

`requirements.txt` には `langgraph` / `langgraph-checkpoint-sqlite` / `google-genai` も含まれており、上記コマンド一発でインストールされます。

### 2. 環境変数の設定

`cp .env.example .env` を実行し、[Google AI Studio](https://aistudio.google.com/) で取得した API キーを設定します。

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. 関心事の登録 (オプション)

`my_status.txt` をプロジェクトルートに作成し、関心のあるキーワードを1行で入力します。

```text
今週の関心: Next.js, 音楽生成AI
```

### 4. 実行

```bash
python3 main.py
```

実行状態は `checkpoints.sqlite`（`.gitignore` 済み）に永続化されます。同日中に再実行すると、`thread_id`（日付ベース）が同じであれば途中から再開されます。

---

## 🎨 LangGraph Studio でグラフを確認する

`langgraph-cli` は Python 3.11 以上が必要です。開発機のPythonが3.10系でも、[uv](https://docs.astral.sh/uv/) で一時環境を作れば `requirements.txt` を変更せずに確認できます。

```bash
uv run --python 3.11 --with-requirements requirements.txt --with "langgraph-cli[inmem]" \
  -- langgraph dev --config langgraph.json
```

起動すると以下が表示されます。

```
- 🚀 API: http://127.0.0.1:2024
- 🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
- 📚 API Docs: http://127.0.0.1:2024/docs
```

Studio UI から `fetch_hn`/`fetch_ph`/`fetch_tc`/`fetch_reddit`/`dispatch`/`analyze_article`/`rank`/`report` の各ノードとグラフ構造を可視化できます。

---

## 📅 毎朝 7 時の自動実行 (cron / PC起動時)

自動起動用シェルスクリプト `scripts/run_daily.sh` は、二重実行を防止する「冪等ガード」が組み込まれており、当日分のMarkdownレポートが既に存在する場合は何もしません。

### 1. スクリプトの実行権限付与

```bash
chmod +x scripts/run_daily.sh
```

### 2. crontab への登録 (毎朝 7:00 実行)

```bash
crontab -e
```

以下の1行を追加します（パスはご自身の環境に合わせて変更してください）。

```text
0 7 * * * /absolute/path/to/leanshift-trend-bot/scripts/run_daily.sh
```

### 3. PC 起動時の自動実行設定 (anacron の代替)

cronはPC電源がOFFのときには実行されません。午前7時以降にPCを起動した際にも自動で当日分を実行させたい場合は、`~/.bashrc` の末尾に以下を追加します。

```bash
bash /absolute/path/to/leanshift-trend-bot/scripts/run_daily.sh &
```
> ※ `&` を末尾に付けることで、シェルの起動速度を落とさずバックグラウンドで非同期実行させます。

---

## 📝 outputs/ 出力レポートのサンプル

分析結果は `outputs/YYYY-MM-DD_trends.md` に以下の形式で自動生成されます。

```markdown
# Trend Report — 2026-08-14

## ユーザーステータス

今週の関心: Next.js, 音楽生成AI

---

## 第 1 位 — [Hacker News] AIの未来はOSSにあり？

- **元記事:** Open source AI must win
- **URL:** https://opensourceaimustwin.com/?share=v2
- **🔥 バズ度:** ⭐⭐⭐⭐ (4/5)

### 要約

オープンソースAIの重要性と、それが業界をリードすべき理由を論じる記事。透明性やカスタマイズ性の観点から、
海外テックコミュニティで活発に議論されています。

### 📝 Zenn構成案

**タイトル:** 【徹底議論】なぜオープンソースAIが勝たねばならないのか？

**見出し構成:**
- 1. はじめに：AIの現状とオープンソース
- 2. OSSのメリット：透明性とカスタマイズ性
- 3. 音楽生成AIなど創作分野におけるオープンソースの可能性
- 4. プロプライエタリAIとの対比
- 5. まとめ

**導入文:**
近年クローズドなAIモデルが急成長していますが、実はオープンソースAIこそが今後のイノベーションの本命であるとする議論が活発です。その理由を紐解きます。

**タグ:** `AI` / `OSS` / `テクノロジー`

### マネタイズアイデア

オープンソースAIモデルの商用利用ライセンス販売、または関連する構築・運用コンサルティング。

### 📣 X投稿下書き

```text
🎨 オープンソースAIの重要性を説く記事を発見しました！
透明性、カスタマイズ性、コミュニティ主導のイノベーションが鍵。音楽生成AIの未来にも期待が高まりますね。
https://opensourceaimustwin.com/?share=v2
```

---
```

---

## 🧪 テストと品質管理

コードを変更した際は、必ず以下の静的解析およびテストを実行し、エラーのない状態を維持してください。

```bash
# 静的型チェック (mypy)
python3 -m mypy .

# 単体テスト (pytest)
python3 -m pytest -v
```

---

## 📂 設計ドキュメント (docs/)

*   [ARCHITECTURE.md](docs/ARCHITECTURE.md) — 移行前（線形パイプライン時代）のアーキテクチャ概要。現行のLangGraph構成は下記の設計書を参照
*   [superpowers/specs/2026-08-14-langgraph-migration-design.md](docs/superpowers/specs/2026-08-14-langgraph-migration-design.md) — LangGraph移行設計書（core/orchestration分離、グラフフロー、State設計）
*   [superpowers/plans/2026-08-14-langgraph-migration.md](docs/superpowers/plans/2026-08-14-langgraph-migration.md) — LangGraph移行の実装計画（18タスク、TDD）
*   [DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) — 開発・テスト手順、エージェント二刀流の役割分担
*   [CHANGELOG.md](docs/CHANGELOG.md) — gitコミットベースの機能変更履歴
*   [gemini_prompt_v2_draft.md](docs/gemini_prompt_v2_draft.md) — Geminiシステムプロンプト設計（移行前のドラフト）
*   [prompt_fewshot_examples.md](docs/prompt_fewshot_examples.md) — プロンプト出力を安定させるFew-Shotサンプル例
*   [ranking_logic_design.md](docs/ranking_logic_design.md) — 関心度順位付けのスコアリング基準とエッジケース設計
*   [ranking_batch_design.md](docs/ranking_batch_design.md) — 旧・一撃バッチ処理設計（移行前）
*   [viral_title_design.md](docs/viral_title_design.md) — 日本語タイトル改善の5大バズ法則
*   [mvp_checklist.md](docs/mvp_checklist.md) — MVP開発進捗・未完了タスク状況
