# leanshift-trend-bot — Claude Code 開発憲法

## 🚨 憲法①：静的型チェックをテスト代わりにする

本プロジェクトは Python + Pydantic を採用している。
コードを追加・修正・リファクタリングしたら、**必ず完了報告の前に `mypy .` を実行**し、
型エラーが 0 件であることを確認すること。型エラーが残った状態での実装完了は認めない。

```
python3 -m mypy .
```

## 🚨 憲法②：AIパース処理には必ず pytest 単体テストを書く

`RawArticle → ProcessedDraft` の変換ロジック、外部 API 連携のコアロジックなど
**複雑なロジックを実装した際は、自分（Claude Code）自身が pytest テストを書く**こと。
周辺コードを触る際は必ず `pytest` を実行してパスを確認すること。

```
python3 -m pytest
```

### テスト対象の目安
- `analyzer.py` のパースロジック（RawArticle → ProcessedDraft マッピング）
- 外部 API レスポンスのバリデーション処理
- 将来追加される音楽・投資・WordPress 連携のコアロジック

### テスト不要な対象
- `fetcher.py` などの外部 I/O 呼び出し自体（モックが複雑になるだけ）
- `models.py` の Pydantic モデル定義（Pydantic が保証する）

## データモデル

`models.py` は**変更不可のマスター**。`RawArticle` と `ProcessedDraft` の定義は一切変えない。
新しいデータソース（音楽・投資・X 等）が増えても必ずこのモデルに適合させる。
