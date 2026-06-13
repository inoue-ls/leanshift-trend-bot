# leanshift-trend-bot

Hacker News の海外テックトレンドを **Gemini 2.5 Flash Lite** で自動分析し、日本向けの起業ネタ・Zenn 記事構成案・マネタイズアイデアをターミナルに出力するボットです。

## デモ出力

```
============================================================
  leanshift-trend-bot  |  Hacker News → 日本語ビジネスアイデア
============================================================

[1/3] Hacker News から上位 3 件を取得中...
      3 件取得完了

[2/3] Gemini 2.5 Flash Lite で分析中...
      3 件の分析完了

[3/3] 結果を表示します
============================================================

【記事 1】Solar generates more energy in US than coal for first time
  URL: https://...

  ▶ 一言要約
    太陽光発電が初めて石炭火力発電を上回り、米国の主要な電力源としての地位を確立した。

  ▶ 背景分析
    近年、米国では再生可能エネルギーへのシフトが加速しており...

  ▶ Zenn 記事構成案
    【速報】米国のエネルギー事情が激変！太陽光発電が石炭を初めて上回った理由
    ...

  ▶ マネタイズアイデア
    家庭用・産業用太陽光発電システムの導入コンサルティング...
```

## 技術スタック

| 役割 | ライブラリ |
|---|---|
| AI 分析 | [Google Gemini 2.5 Flash Lite](https://ai.google.dev/) (`google-genai`) |
| データ取得 | Hacker News RSS (`feedparser`) |
| データモデル | `pydantic` v2 |
| 環境変数 | `python-dotenv` |
| 型チェック | `mypy` |
| テスト | `pytest` |

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/inoue-ls/leanshift-trend-bot.git
cd leanshift-trend-bot
```

### 2. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

### 3. API キーを設定

```bash
cp .env.example .env
```

`.env` を開き、[Google AI Studio](https://aistudio.google.com/) で取得した API キーを設定します。

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. 実行

```bash
python3 main.py
```

## プロジェクト構成

```
leanshift-trend-bot/
├── main.py          # エントリーポイント（フルパイプライン）
├── fetcher.py       # Hacker News RSS からの記事取得
├── analyzer.py      # Gemini API による構造化分析
├── models.py        # Pydantic データモデル（変更不可マスター）
├── requirements.txt
├── mypy.ini
├── .env.example     # API キーのテンプレート
└── tests/
    └── test_analyzer.py  # パースロジックの単体テスト
```

## データモデル

```
RawArticle（生データ）
  └─ article_id, source_name, category, title, url, summary, collected_at

ProcessedDraft（AI 処理済み）
  └─ draft_id, article_id,
     one_line_summary, background_analysis,
     zenn_article_structure, monetization_idea,
     processed_at
```

`models.py` はすべてのデータソース（音楽・投資・X 等）が増えても変更しないマスター定義です。

## 自動実行（毎朝 7 時 cron）

`scripts/run_daily.sh` がプロジェクトルートへ `cd` し、`.env` を読み込んで `python3 main.py` を実行します。  
ログは `logs/YYYY-MM-DD.log` に追記されます。

### 1. スクリプトに実行権限を付与

```bash
chmod +x scripts/run_daily.sh
```

### 2. crontab に登録

```bash
crontab -e
```

エディタが開いたら以下の 1 行を追加して保存します（パスは環境に合わせて変更）。

```
0 7 * * * /home/saishin/gtd/03_projects/leanshift-trend-bot/scripts/run_daily.sh
```

### 3. ログの確認

```bash
cat logs/$(date +%Y-%m-%d).log
```

### 4. PC 起動時に自動実行する（anacron 代替）

cron は「PC が起動していない時刻」には実行されません。  
7 時を過ぎてから PC を起動した日でも当日分を生成するには、  
`~/.bashrc`（または `~/.bash_profile`）に以下の **1 行** を追加します。

```bash
bash /home/saishin/gtd/03_projects/leanshift-trend-bot/scripts/run_daily.sh &
```

> - `&` を付けてバックグラウンド実行にすることでシェルの起動を妨げません。  
> - `run_daily.sh` には冪等ガードが組み込まれており、当日分の  
>   `outputs/YYYY-MM-DD_trends.md` がすでに存在する場合は即座に終了します。  
>   cron（7 時実行済み）と起動時実行が重複しても二重生成にはなりません。

---

## 開発

```bash
# 型チェック
python3 -m mypy .

# テスト
python3 -m pytest -v
```
