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

## Stack
- Python 3.10 + Pydantic. Run tests with `python3 -m pytest -v` and type-check with `python3 -m mypy .` (0 errors, constitution ①) before you report.
- Tests live under `tests/`, mirroring the source tree (this overrides "next to the source" below).
- `spec.json` is the record of the retired `/spec-cycle` pipeline (past pains, assumptions, features). Read it for background; don't update it.

## How to build
- Build only what the request states. List ideas the request does not state as proposals in your reply; don't build them.
- Build the whole request in one go, end to end. Don't leave a stated part for later unless the request says so.
- Write a failing test first and show it failing on an assertion, then write the minimal code that passes it. Tests live next to the source.
- Every test asserts real output, state, or a specific error. Never mock the unit under test; pass external I/O (HTTP, DB, clock, randomness) in as an argument so tests can replace only that.
- Never edit, delete, skip, or weaken existing tests. Run all tests before you report; every test must pass.
- Don't change the behavior or signature of existing functions unless the request asks for it; add a new one instead.
- Build a screen only when the request asks for one: one screen, one action, no styling, plus the command to open it.
- Report the assumptions you made for facts the request did not give.

## Git and secrets
- When a request is done, commit it. Stage with `git add -u` plus explicit paths for new files; `git add .` / `-A` / `--all` are blocked by `.claude/hooks/guard-bash.py`.
- `.env*` is never read into context or committed.
- Destructive commands (`rm -rf` on broad paths, `git push --force`, `git reset --hard`, `DROP TABLE`, ...) are blocked by `.claude/hooks/guard-bash.py` anywhere in a chained command. After changing the hook, run `python3 -m unittest discover -s .claude/hooks -p 'test_*.py'`.
