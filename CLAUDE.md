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

## Runtime
- No language, framework, or library is fixed up front. Cycle 1 of `/spec-cycle` picks the smallest runtime that solves the pain and records it in `spec.json` -> `runtime`.
- Run tests and formatting only through `runtime.test_command` / `runtime.format_command`.
- Test file placement follows `runtime.test_file_convention` (tests live next to source).
- Existing stack: Python 3.10 + Pydantic. Cycle 1 must set runtime accordingly (`test_command`: `python3 -m pytest -v` — sentry needs per-test output, tests under `tests/` mirroring the source tree), pass `python3 -m mypy .` with 0 errors (constitution ①), and never modify `models.py`.

## Autonomous pipeline (Tesla-style vibe coding)
- `/spec-cycle` is the single entry point (`.claude/skills/spec-cycle/`). `/spec-cycle "<pain>"` runs one sprint end-to-end: requirements & scope reduction -> `spec.json` (single source of truth) -> `builder` (TDD) / `sentry` (gatekeeper) with a self-healing loop capped at 3 retries -> baseline update. Run with no args to advance the next backlog item.
- All autonomous work happens on the throwaway branch `vibe/temp-feature`. Never run the pipeline directly on `main`, and never in this template repository (`gate.py preflight` stops when `setup/gen_apply_doc.py` exists); for a trial run, `python3 setup/trial.py` creates a throwaway product repository with the template applied.
- Red must fail on an assertion. New interfaces start as stubs that return an empty value of the declared type, never as stubs that raise.
- Roles: `planner` decides what to build (Phase A), `builder` writes tests and code, `sentry` is the only reviewer: a mechanical SHIP / RETRY / HALT gate (security, test / spec tampering, tests, over-engineering, boundary breaks). The orchestrator only runs the mechanics and passes each subagent the output of `.claude/skills/spec-cycle/brief.py` unchanged; it never adds implementation hints or tells sentry how to judge. Its checks (Step 0 preflight, the B-0 baseline, HEAD pinning, tree snapshots, a clean tree after every commit, the planner's footprint and HEAD, allowed commands, re-running the tests named by the Red builder and by sentry after reinstalling dependencies) are `gate.py` subcommands, not hand-run shell steps. Commands from `spec.json` pass `guard-bash.py` in both `check_spec.py` and `gate.py`, because `gate.py` runs them outside the Bash hook.
- Scope stays inside the pain: every pain is recorded verbatim in `spec.json` -> `pains`, and the increment and every backlog item must quote it (`source`). A quoted phrase backs one increment only: a source may not overlap a completed feature's source, so a follow-up needs a new pain. Ideas the pain does not state go to `proposals`, never the backlog. Backlog items leave only by completion or through `dropped_backlog` with evidence.
- `spec.json` is validated by `.claude/skills/spec-cycle/check_spec.py --against HEAD` after every write: schema (`spec-schema.json`), state rules, that each completed feature's `file` / `symbol` exists, and invariants against the previous spec.
- Tests and the test harness (`runtime.harness_files`: manifest, lockfile, runner config, conftest) are written and committed first (Red, verified mechanically by `gate.py verify-evidence`; `sentry` runs once per cycle, after Green, and reviews the Red and Green diffs together); the implementation (Green) must pass them without modifying any of them. The orchestrator records the spec and Red commit hashes and HALTs if `HEAD` moves; `guard-bash.py` blocks `commit --amend` / `reset` / `rebase` while `vibe/temp-feature` is checked out.
- The pipeline never edits `.claude/` (no self-granted permissions). `gate.py` runs `spec.json` commands without a permission prompt, so it only runs a single command that matches `permissions.allow` (and no deny rule) in `.claude/settings.json` / `settings.local.json`; otherwise the cycle HALTs with the allow-list lines for a human to add.
- `runtime` is fixed after Cycle 1, except that a later cycle may add one dependency when the increment cannot be built with the standard library and existing dependencies.
- On 3 failed attempts in a phase, or immediately on a security HALT, the pipeline auto-rolls back (tag the branch tip as `vibe/failed/<timestamp>`, `git checkout -f <base>`, delete branch, `git clean -fd`) and stops. Because of that clean, it refuses to start on a dirty working tree.
- `spec.json` -> `current_baseline.features` accumulates one entry per completed cycle; entries are never overwritten.
- Deleting a feature is not a `/spec-cycle` run: when a human asks for it, do it on the base branch (e.g. `main`) and show the diff before committing. In one commit: remove its code and tests, remove its entry from `current_baseline.features`, add `{"item": ..., "keyword": ...}` to `wont`, and remove backlog items that depend on it. The `wont` entry is what keeps it deleted: once its feature entry is gone, its pain phrase can be quoted again, but planner never promotes a `wont` item and sentry rejects code for one. Leftover tests or feature entries make the next cycle stop, not rebuild.
- **No fake tests:** every test asserts real output / state / thrown errors. Never mock the unit under test. No `expect(true).toBe(true)`.
- Failure logs are truncated to the first ~30 lines before being passed between agents.
- Secrets: `.env*` is never read into context or committed. Stage with `git add -u` plus explicit paths for new files; `git add .` / `-A` / `--all` are blocked by `guard-bash.py`.
- Destructive commands (`rm -rf`, `git push --force`, `git reset --hard`, `DROP TABLE`) are denied in `.claude/settings.json`. `.claude/hooks/guard-bash.py` also blocks them anywhere in a chained command; the only forced checkout / clean it lets through is the exact rollback chain. After changing the hook, `check_spec.py`, `brief.py`, `gate.py`, or the rollback block in `SKILL.md`, run `python3 -m unittest discover -s .claude/hooks -p 'test_*.py'` and `python3 -m unittest discover -s .claude/skills/spec-cycle -p 'test_*.py'`.
