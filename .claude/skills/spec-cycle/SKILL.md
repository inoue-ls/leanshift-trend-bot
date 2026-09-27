---
description: spec.json を唯一の真実として、要件定義（スコープ縮退）→ TDD 実装 → ベースライン更新までを1スプリント分自律実行する
disable-model-invocation: true
argument-hint: "[現場ペイン1行 — 省略時は spec.json の next_sprint_backlog 先頭を進める]"
---

# Spec Cycle: 要件定義 → 自律実装 1スプリント完全版

入力: $ARGUMENTS

リポジトリ直下の `spec.json` を唯一の真実（Single Source of Truth）とする。
Phase A（What / Why）と Phase B（How）を人間の介在なしで一気通貫に実行する。
途中で人間に「どうしますか？」と質問しない。判断はテスト結果と spec.json のファクトのみに基づく。

## 現在の状態

- ブランチ: !`git branch --show-current`
- 作業ツリー: !`git status --porcelain | head -n 20`
- spec.json: !`cat spec.json 2>/dev/null || echo "(なし)"`

---

## Step 0: 前提チェックと隔離

以下のいずれかに該当したら、理由を1行出力して **即停止** する。

1. 作業ツリーが dirty（上の `git status --porcelain` が空でない）。ロールバックで `git clean -fd` を使うため、未コミットの成果物を巻き込まない。→「commit か stash してから再実行してください」
2. 入力が空 かつ `spec.json` が存在しない。→「初回は現場ペインを1行渡してください」
3. 入力が空 かつ `spec.json.next_sprint_backlog` が空。→「バックログが空です。新しいペインを渡してください」
4. 既存の `vibe/temp-feature` が未マージ（`git branch -d vibe/temp-feature` が失敗する）。前スプリントの成果を消さない。→「前回の vibe/temp-feature をマージしてから再実行してください」

通過したら:

```bash
git branch --show-current        # 戻り先 <base> として記録
git branch -d vibe/temp-feature 2>/dev/null; git checkout -b vibe/temp-feature
```

---

## Phase A: 要件定義 & スコープ縮退（エージェントA）

`agent-a.md` のルールに従い、次スプリントの `spec.json` を生成する。スキーマは `spec-schema.json`。

- **初回（spec.json なし、入力 = ペイン）:** `cycle_type: "cycle_1_tracer"`。ペインから過剰仕様を削除し、Tracer Bullet を1本だけ定義する。あわせてペインを解く最小の言語・実行環境を決め、`runtime` に記録する。
- **拡張（spec.json あり、入力なし）:** `cycle_type: "cycle_n_expansion"`。`current_baseline` を保持したまま、`next_sprint_backlog` の先頭1件だけを `target_increment` に昇格させる。
- **拡張 + 新ペイン（spec.json あり、入力あり）:** ペインを縮退させて `next_sprint_backlog` に優先度順で差し込み、その先頭1件を昇格させる。既存の `current_baseline` と `wont` は壊さない。

出力ルール:

- `status` は `"ready_for_implementation"`。
- `target_increment` の関心事は **1つだけ**。複数混在していたら削ぎ落とし、残りを `next_sprint_backlog` へ。
- `wont` に該当する要望は昇格させない。
- `runtime` は Cycle 1 で決めたら以降のサイクルでは変更しない。
- `spec.json` を書き込んだら、仕様だけを先にコミットする（実装失敗時も仕様の差分が追える）:

  ```bash
  git add spec.json && git commit -m "spec: <feature_name> (<cycle_type>)"
  ```

---

## Phase B: 設計 & 自律実装（エージェントB）

### B-0: 現状確認

- テストが既に存在する場合（Cycle 2 以降）、`runtime.test_command` を実行し、既存テストが All Green であることを確認する。Red なら実装を始めず HALT（ロールバックへ）。
- Cycle 1 のみ、`runtime` に記録した言語のテストランナーの最小セットアップを B-1 の一部として許可する（標準ライブラリで足りるならそれを使う）。これ以外の依存追加は禁止。

### B-1 → B-2: builder に委譲（Red → Green）

Agent ツールで `builder` サブエージェントを起動し、以下を渡す:

- `spec.json` の `runtime` / `target_increment` / `execution_steps` / `wont` / `current_baseline.interface`
- テストは `runtime.test_file_convention` に従って配置する
- 指示:
  1. **Red First:** `acceptance_criteria`（given / when / then）を検証する最小テストを書き、`runtime.test_command` で **意図通り失敗する** ことを確認する。既存テストは壊さない。
  2. **Green:** テストを通す物理最小限のプレーンコードを書く。新規抽象クラス・過剰な例外処理・未指定のライブラリ追加は禁止。
  3. **No fake tests:** 実際の出力値・状態・throw を assert する。テスト対象自身をモックしない。`expect(true).toBe(true)` 禁止。
  4. `wont` の項目は実装しない。
  5. 作成・変更したファイルパスを一覧で報告する。

### B-3: sentry で検証 & 自己修復ループ（最大3回）

Agent ツールで `sentry` サブエージェントを起動し、試行回数を渡す。sentry はテスト実行と差分の機械的レビュー（セキュリティ・過剰設計・境界破壊）を行い、`SHIP | RETRY | HALT` を返す。別のレビュアーエージェントは使わない。

- **SHIP:** B-4 へ。
- **RETRY（試行回数 < 3）:** sentry の Issues（最大3行）と、あれば失敗ログ（先頭30行）**だけ** を builder に渡して修正させ、sentry を再実行する。
- **RETRY が3回目 または HALT（セキュリティ欠陥は即時）:** ロールバックして停止する。

  ```bash
  git checkout -f <base> && git branch -D vibe/temp-feature && git clean -fd
  ```

  `[FATAL] spec-cycle halted (<gate>, attempt <n>/3). Rolled back to <base>.` と、最終試行の Issues と失敗ログを出力して停止する。

### B-4: spec.json 自律更新 & コミット

全 Green を確認したら `spec.json` を更新する:

- `status`: `"completed"`
- `current_baseline.completed_feature`: 今回実装した機能の事実（関数名・ファイルパス含む）
- `current_baseline.test_status`: `"all_green"`
- `current_baseline.interface`: 今回確定した入出力の型
- `target_increment`: 各フィールドを空文字（`acceptance_criteria` は空の given/when/then）にクリア
- `next_sprint_backlog`: 今回完了した項目を削除し、残りは順序を維持

コミット（`git add .` は禁止。新規ファイルは builder の報告したパスを明示指定する）:

```bash
<runtime.format_command>   # 空ならスキップ
git add -u && git add <builder が新規作成したファイル...>
git commit -m "feat(spec-cycle): <feature_name> [auto-verified]"
```

`.env*` が staging に含まれていないことを `git diff --cached --name-only` で確認してからコミットする。

---

## 完了レポート

以下だけを出力して終了する:

1. ブランチ: `vibe/temp-feature`（マージは人間が動作確認後に行う）
2. 今回の Increment: `feature_name` / `focus`
3. 作成・通過したテスト
4. 変更ファイルとコミットハッシュ
5. 次スプリント候補: `next_sprint_backlog` の先頭
6. 次の一手: `vibe/temp-feature` を <base> にマージ → 再度 `/spec-cycle` を実行

## 禁止事項

- `main` 上での直接実装（必ず `vibe/temp-feature`）
- テストが Red のまま終了すること
- `wont` 記載項目の実装
- 人間への質問（Step 0 の停止条件を除く）
