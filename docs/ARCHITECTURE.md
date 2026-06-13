# プロジェクト・アーキテクチャ概要書 (ARCHITECTURE)

本書は、`leanshift-trend-bot` の全体像、データフロー、各モジュールの責務、および設計書の一覧をまとめた、**新メンバーが3分でシステム全体を把握できるためのオンボーディングガイド** です。

---

## 1. システム概要（30秒クイックピッチ）

`leanshift-trend-bot` は、4つの海外テックソースから最新の技術ニュースを計12件取得し、ユーザーの現在の関心（`my_status.txt`）に基づいて **Gemini 2.0 Flash（一撃バッチAPIコール）** で順位付け・要約・X（旧Twitter）用の投稿下書き作成を一撃で行い、個人知識ベース（Obsidian等）にMarkdownレポートとして自動保存する自動トレンドキュレーションシステムです。

---

## 2. 全体データフロー（ASCIIアート）

システム起動（`python3 main.py`）からレポート保存・活用までのデータの流れです。

```
[ 4つのRSSニュースソース ] (Hacker News, Product Hunt, TechCrunch, Reddit)
        │
        ▼ (1. RSS購読: 各3件ずつ取得)
[ fetcher.py ]  ───► (2. クレンジング: _strip_html でHTMLタグを除去)
        │
        ▼ (3. RawArticle モデルのリスト: 計12件)
[ main.py ]  ◄───► [ my_status.txt ] (4. ユーザー関心度ロード)
        │
        ▼ (5. XML構造のバッチプロンプトとして一括送信)
[ analyzer.py ] ───► [ Gemini 2.0 Flash ] (6. 1回のバッチAPIコール)
        │                    │
        │                    ▼ (7. 順位順にソートされた構造化JSON)
[ analyzer.py ] ◄─── (8. レスポンスパース & Pydanticバリデーション)
        │
        ▼ (9. 順位順の ProcessedDraft のリスト)
[ main.py ]
        │
        ├─► [ ターミナル出力 ] (10. コンソールでの整形表示)
        │
        ▼ (11. レポート保存)
[ outputs/YYYY-MM-DD_trends.md ]
        │
        ▼ (12. 連携・ストック)
[ Obsidian / ナレッジベース ]
```

---

## 3. ファイルの責務一覧テーブル

プロジェクトを構成する主要ファイルの役割分担です。

| ファイル名 | 役割（責務） | 主な実装内容 / コアロジック |
| :--- | :--- | :--- |
| [models.py](file:///home/saishin/gtd/03_projects/leanshift-trend-bot/models.py) | **変更不可のデータ定義マスター** | 全モジュールで共通して利用される Pydantic モデル定義 (`RawArticle`, `ProcessedDraft`)。拡張時も不変。 |
| [fetcher.py](file:///home/saishin/gtd/03_projects/leanshift-trend-bot/fetcher.py) | **データ収集 & クレンジング** | 4つのRSSソースからの並行取得、`feedparser` によるパース、およびサマリーからHTMLタグを除去する `_strip_html`。 |
| [analyzer.py](file:///home/saishin/gtd/03_projects/leanshift-trend-bot/analyzer.py) | **AI構造化分析 (Gemini連携)** | 関心事と12記事の結合プロンプト組み立て、`google-genai` SDK を用いたAPI接続、一括JSONのパース。 |
| [main.py](file:///home/saishin/gtd/03_projects/leanshift-trend-bot/main.py) | **実行オーケストレーター** | システムの起動制御、`my_status.txt` の読込、収集・分析パイプラインの調整、および最終Markdownファイルの書込。 |

---

## 4. `docs/` 内の設計ドキュメント一覧と用途

本プロジェクトの各機能拡張の根拠とプロンプト設計が記されたファイルの一覧です。

```
docs/
├── ARCHITECTURE.md            # 本書：全体構造の俯瞰とオンボーディングガイド
├── gemini_prompt_v2_draft.md  # システムプロンプト設計書 (JSON/Markdownの2パターン定義)
├── prompt_fewshot_examples.md # Few-Shot具体例集 (5つのテック領域におけるGeminiの出力安定化用データ)
├── ranking_logic_design.md    # 順位付けアルゴリズム設計書 (加重平均根拠と4種類のエッジケース対策)
├── ranking_batch_design.md    # 一括バッチ処理設計書 (1回コールへの移行、APIコスト・性能比較シミュレーション)
├── viral_title_design.md      # バズるタイトル設計書 (5つのバズる法則、バズ度評価、X投稿下書きへの統合案)
└── mvp_checklist.md           # 開発状況チェックリスト (現状分析とE2E実走に向けたPython側改修タスク)
```

---

## 5. 新メンバーへ：次に開発・確認すべきこと

あなたがこのプロジェクトに参加し、開発を進める場合の最短ルートです。

1. **環境のセットアップ**: `.env` を作成し `GEMINI_API_KEY` を設定します。
2. **型とテストの確認**: `python3 -m mypy .` と `python3 -m pytest -v` を実行し、既存テストがパスすることを確認します。
3. **バッチ化の実施**: [mvp_checklist.md](file:///home/saishin/gtd/03_projects/leanshift-trend-bot/docs/mvp_checklist.md) の「3. エンドツーエンド実走成功に向けた残タスク」を順にコード（`analyzer.py` / `main.py`）に適用します。
4. **プロンプトの調整**: [ranking_batch_design.md](file:///home/saishin/gtd/03_projects/leanshift-trend-bot/docs/ranking_batch_design.md) および [viral_title_design.md](file:///home/saishin/gtd/03_projects/leanshift-trend-bot/docs/viral_title_design.md) に従って、一撃で高精度な JSON が返却されるように `_SYSTEM_PROMPT` をアップデートします。

---
*作成日: 2026年6月13日*
*作成元: Advanced Agentic Coding Team (Antigravity)*
