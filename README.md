# leanshift-trend-bot

海外テックフィードの最新トレンド記事を **Gemini 2.0 Flash（一撃バッチAPIコール）** で自動分析・順位付けし、日本語の起業アイデア、Zenn用ブログ構成、およびX（旧Twitter）投稿用下書きを自動生成するキュレーションシステムです。

---

## 🚀 主要機能 (6大機能 ＋ Zennドラフト)

1.  **4つの主要テックソースからの自動収集**
    *   Hacker News (points>=200)、Product Hunt、TechCrunch Startups、Reddit r/webdev からそれぞれ3件、計12件の記事を自動取得。
2.  **HTMLクレンジングによる不要ノイズ除去**
    *   RSSのサマリーに含まれる不要なHTMLタグを自動的にクレンジングし、APIトークン消費量を節約。
3.  **ユーザーステータス（my_status.txt）連携**
    *   `my_status.txt` に書かれた「今週の関心」を自動で読み込み、AI解析の切り口や優先順位をパーソナライズ。
4.  **一撃バッチ分析と相対順位付け（API消費8割カット＆3倍速化）**
    *   12記事を一括でGemini 2.0 Flashへ送信。記事全体の相対評価を行い、ユーザーの関心にマッチした順（1位〜12位）に自動ソート。
5.  **バズ度評価（1〜5）と日本語タイトル改善**
    *   日本のテックコミュニティ（X、Zenn、はてブ）での拡散力を5段階でスコアリング。「バズるタイトルの法則」に則った日本語タイトル改善案を提案。
6.  **URL対応のX（旧Twitter）投稿下書き自動生成**
    *   元のURLプレースホルダーを末尾に含め、絵文字フックを用いた100〜130文字（日本語）のSNSドラフトを自動生成。
*   **【統合機能】Zenn記事構成案（ZennDraft）の作成**
    *   ブログ記事の仮タイトル、見出し構成（H2以下）、キャッチーな導入文、および関連タグを自動生成。

---

## 💻 デモ出力（コンソール）

```text
============================================================
  leanshift-trend-bot  |  4ソース → 日本語ビジネスアイデア
============================================================

[ユーザーステータス] 今週の関心: Next.js, 音楽生成AI

[取得 1/4] Hacker News から上位 3 件を取得中...
      3 件取得完了
...
合計 12 件のデータ取得完了

[分析] Gemini 2.0 Flash で一括バッチ分析中（1回のAPIコール）...
      12 件の分析完了（関心度順にソート済み）

[結果] 分析結果を表示します（関心度順）
============================================================

【第 1 位】⭐⭐⭐⭐⭐ [Hacker News] AIの未来はOSSにあり？
  元記事: Open source AI must win
  URL: https://opensourceaimustwin.com/?share=v2

  ▶ 一言要約
    オープンソースAIの重要性と、それが業界をリードすべき理由を論じる記事。

  ▶ 背景分析
    AIの発展においてOSSが果たすべき透明性やカスタマイズ性について論じています...

  ▶ Zenn 記事構成案
    タイトル: 【徹底議論】なぜオープンソースAIが勝たねばならないのか？
    見出し構成:
    - 1. はじめに：AIの現状とオープンソース
    - 2. OSSのメリット：透明性とカスタマイズ性
    - 3. 音楽生成AIなど創作分野におけるオープンソースの可能性
    ...

  ▶ マネタイズアイデア
    オープンソースAIモデルの商用利用ライセンス販売、または関連する構築・運用コンサルティング。

  ▶ X投稿下書き
    🎨 オープンソースAIの重要性を説く記事を発見しました！
    透明性、カスタマイズ性、コミュニティ主導のイノベーションが鍵。音楽生成AIの未来にも期待が高まりますね。
    https://opensourceaimustwin.com/?share=v2
------------------------------------------------------------
...

[保存完了] outputs/2026-06-14_trends.md
```

---

## 🛠️ セットアップと実行手順

### 1. 依存関係のインストール

```bash
git clone https://github.com/inoue-ls/leanshift-trend-bot.git
cd leanshift-trend-bot
pip install -r requirements.txt
```

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

分析結果は `outputs/YYYY-MM-DD_trends.md` に以下の美しい形式で自動生成されます。

```markdown
# Trend Report — 2026-06-14

## ユーザーステータス

今週の関心: Next.js, 音楽生成AI

---

## 第 1 位 — [Hacker News] AIの未来はOSSにあり？

- **元記事:** Open source AI must win
- **URL:** https://opensourceaimustwin.com/?share=v2
- **🔥 バズ度:** ⭐⭐⭐⭐⭐ (5/5)

### 一言要約

オープンソースAIの重要性と、それが業界をリードすべき理由を論じる記事。

### 背景分析

AIの発展においてOSSが果たすべき透明性やカスタマイズ性について論じています...

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

機能拡張の根拠やAIプロンプト設計は `docs/` に格納されています。

*   [ARCHITECTURE.md](docs/ARCHITECTURE.md) — アーキテクチャ構成・データフロー・モジュールの責務
*   [DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) — 開発・テスト手順、エージェント二刀流の役割分担
*   [CHANGELOG.md](docs/CHANGELOG.md) — gitコミットベースの機能変更履歴
*   [gemini_prompt_v2_draft.md](docs/gemini_prompt_v2_draft.md) — Gemini 2.0 Flash システムプロンプト設計
*   [prompt_fewshot_examples.md](docs/prompt_fewshot_examples.md) — プロンプト出力を安定させるFew-Shotサンプル例
*   [ranking_logic_design.md](docs/ranking_logic_design.md) — 関心度順位付けのスコアリング基準とエッジケース設計
*   [ranking_batch_design.md](docs/ranking_batch_design.md) — 一撃バッチ処理移行・Pydanticスキーマ設計・コスト計算
*   [viral_title_design.md](docs/viral_title_design.md) — 日本語タイトル改善の5大バズ法則
*   [mvp_checklist.md](docs/mvp_checklist.md) — MVP開発進捗・未完了タスク状況
