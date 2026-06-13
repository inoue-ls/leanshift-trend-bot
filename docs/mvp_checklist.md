# MVP 開発状況チェックリスト (mvp_checklist)

本書は、`leanshift-trend-bot` の機能開発における Phase 1 から現在までの開発進捗、および「欲しい機能リスト1〜6」の実装状況と、今後エンドツーエンド（E2E）の実走を成功させるために必要な残タスクを整理したチェックリストです。

---

## 1. 完成済み機能（Phase 1 〜 現在）

これまでに実装され、動作確認または単体テストが完了している機能は以下の通りです。

*   **多ソースRSSフィード取得機能** (`fetcher.py`)
    *   Hacker News RSS (`feedparser` による購読、points>=200)
    *   Product Hunt RSS
    *   TechCrunch Startups RSS
    *   Reddit r/webdev RSS (User-Agent偽装対応済み)
    *   各ソースから3件ずつ、合計12件の記事を取得する基盤
*   **HTMLタグクレンジング機能** (`fetcher.py`)
    *   正規表現を用いた `_strip_html` ユーティリティにより、RSSサマリーに含まれるHTMLタグを除去してプレーンテキスト化
*   **Pydantic データモデル定義** (`models.py`)
    *   `RawArticle`（生記事）および `ProcessedDraft`（AI解析済み記事）のスキーマ定義
    *   `x_post_draft`（X投稿用下書き）フィールドを `ProcessedDraft` に追加
*   **ユーザーステータス連携機能** (`main.py` / `analyzer.py`)
    *   `my_status.txt` からユーザーの現在の関心トピックを読み込み、Geminiへのプロンプト入力に動的に差し込む機能 (`_build_user_content`)
*   **Gemini API による個別分析機能** (`analyzer.py`)
    *   `google-genai` SDK を用いた Gemini 接続
    *   個別記事に対する要約・背景分析・Zenn構成案・起業アイデア・X投稿下書きの生成
*   **結果表示＆マークダウンレポート出力機能** (`main.py`)
    *   ターミナルでの整形表示
    *   `outputs/YYYY-MM-DD_trends.md` へのMarkdownレポート自動保存機能
*   **単体テストと静的解析基盤**
    *   `pytest` による Markdown 除去、JSONパース、XML風プロンプトビルドの単体テスト（計12件のテストすべてパス）
    *   `mypy` による静的型チェック設定

---

## 2. 「欲しい機能リスト 1〜6」実装ステータス

新プロンプト案（v2）の要件を踏まえた、現在の実装状況の整理です。

| 番号 | 欲しい機能項目 | 実装状況 | 詳細・現状 |
| :---: | :--- | :---: | :--- |
| **1** | **4ソースからの記事一括取得 (計12件)** | **完了** | `fetcher.py` にて4つのRSSソースから各3件の記事を取得する関数が実装されており、`main.py` で結合して12件のリストにまとめられている。 |
| **2** | **`my_status.txt` に基づく関心ロード** | **完了** | `main.py` で `my_status.txt` を検出し、`analyzer.py` のインプットに連携する機構が動作中。 |
| **3** | **Gemini 2.0 Flash へのモデル移行** | **部分完了** | 現在のコードは `models/gemini-2.5-flash-lite` を使用。一括処理および精度担保のために `gemini-2.0-flash` へのモデル指定の切り替えが必要。 |
| **4** | **12件の記事の一括（一撃）分析** | **未着手** | 現在は `main.py` のループで1記事ずつAPIをコールしている。12件すべてを単一のプロンプト（XML構造）にまとめ、1回のAPIコールで処理する形式へ移行する必要がある。 |
| **5** | **ユーザー関心に基づく順位付け** | **未着手** | 取得順に結果が表示・保存されるのみ。一撃プロンプトの応答に含まれる「順位（rank）」情報をパースし、ソートして表示・保存するロジックが必要。 |
| **6** | **制約を遵守したX用下書きの自動生成** | **部分完了** | フィールド自体は存在するが、文字数（100〜130文字）やフォーマットのブレを防ぐFew-Shot（少発学習例）の組み込みが未実施。 |

---

## 3. エンドツーエンド実走成功に向けた残タスク（チェックリスト）

「Pythonコードは一切触らない」という制約の下、今後 Python 側の実装を拡張して一撃バッチ処理を成功させるための具体的なタスクリストです。

### 📋 1. データモデルの適合性確認と調整 (`models.py`)
*   [ ] `models.py` は変更不可マスターのため、Geminiからの返却値である `rank`（順位）や `evaluation_reason`（評価理由）を、既存の `ProcessedDraft` の中に格納するか、あるいは一時的に別構造でパースしてから `ProcessedDraft` に割り当てる実装設計を決定する。

### 📋 2. 一撃（バッチ）解析ロジックへのリファクタリング (`analyzer.py`)
*   [ ] **モデル名の変更**: `MODEL` 変数を `"gemini-2.0-flash"` に更新する。
*   [ ] **システムプロンプトの更新**: `_SYSTEM_PROMPT` を `docs/gemini_prompt_v2_draft.md` 内の【パターンA（JSON出力版）】に変更する。
*   [ ] **Few-Shot の組み込み**: `docs/prompt_fewshot_examples.md` の内容をシステムプロンプトの末尾、またはAPIリクエストに含めるように結合する。
*   [ ] **一括入力ビルダの実装**: 12件の `RawArticle` の配列と `user_status` を受け取り、`<user_interests>` と `<articles>` のXML風ブロックを作成する `_build_batch_user_content` を実装する。
*   [ ] **APIコール関数の修正**:
    *   `analyze_articles` 内でループを回すのを止め、1回でGemini APIに送信する。
    *   `types.GenerateContentConfig` で `response_mime_type="application/json"` を指定する。
*   [ ] **JSONパースロジックの修正**: `ranked_articles` 配列を含むJSONを受け取り、パースして `ProcessedDraft` のリストに変換・復元するデコード関数（およびエラーハンドリング）を実装する。

### 📋 3. メインフローと表示・保存処理の変更 (`main.py`)
*   [ ] **実行フローの修正**: 一括処理された結果（順位付きのリスト）を `analyze_articles` から受け取る形に変更する。
*   [ ] **順位ベースのソート表示**: ターミナル表示時に、Geminiが評価した `rank`（1位〜12位）の昇順で並び替えて出力する。
*   [ ] **Markdownレポートの出力修正**: `save_markdown_report` を改修し、順位・評価理由・X投稿下書きがきれいにレイアウトされたマークダウン（`docs/gemini_prompt_v2_draft.md` のパターンBに近い形式）で保存されるように変更する。

### 📋 4. テストと品質管理の実行
*   [ ] **単体テストの更新** (`tests/test_analyzer.py`): 一括JSONパース用のテストケースを追加・更新する。
*   [ ] **静的型チェックの実行**: `python3 -m mypy .` を実行し、型エラーが0件であることを確認する（CLAUDE.md憲法①）。
*   [ ] **単体テストの実行**: `python3 -m pytest -v` を実行し、全テストケースがパスすることを確認する（CLAUDE.md憲法②）。

### 📋 5. E2E動作テストの実行
*   [ ] **実環境での疎通確認**: `python3 main.py` を実行し、RSS取得 → Gemini 2.0 Flash 一撃解析 → 順位順のターミナル出力 → Markdown保存が完全に完了することを確認する。

---
*作成日: 2026年6月13日*
