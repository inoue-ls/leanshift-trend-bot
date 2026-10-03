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
パイプラインは `.claude/` 配下（権限・フック・エージェント定義）を一切変更しない。

**オーケストレーター（このスキルを実行するあなた）の役割は機械的な進行だけ。** 何を作るかは `planner`、テストと実装は `builder`、合否は `sentry` が決める。サブエージェントへの prompt は `brief.py` の出力を1文字も変えずに渡す。実装方法の示唆、判定の解釈、補足説明を書き足してはならない（例外は RETRY 時に、Red ではゲートの1行、Green では sentry の Issues と失敗ログを末尾に追記することだけ）。前提チェック・作業ツリーの比較・HEAD の照合・裏取りは、手作業ではなく `gate.py` で行う。`gate.py` が `STOP` / `HALT` を出したら、その1行をそのまま理由として扱う。

## 現在の状態

- ブランチ: !`git branch --show-current`
- 作業ツリー: !`git status --porcelain | head -n 20`
- spec.json: !`cat spec.json 2>/dev/null || echo "(なし)"`

---

## Step 0: 前提チェックと隔離

入力があれば `--pain` を付けて実行する:

```bash
python3 .claude/skills/spec-cycle/gate.py preflight --pain
```

`STOP: ...` が出たら、その1行を出力して **即停止** する。確かめる内容は次のとおり:

1. テンプレートのリポジトリ（`setup/gen_apply_doc.py` がある）ではない。テンプレートに製品のコードを混ぜない。試運転は `setup/apply-spec-cycle.md` で別のリポジトリに導入して行う。
2. 作業ツリーが dirty でない。ロールバックで `git clean -fd` を使うため、未コミットの成果物を巻き込まない。
3. HEAD がブランチを指していて、それが `vibe/temp-feature` 自身でない。ロールバックの戻り先が要る。
4. 入力が空なら、`spec.json` があり、`next_sprint_backlog` が空でない。
5. 既存の `vibe/temp-feature` があれば、HEAD にマージ済みである。前スプリントの成果を消さない。

`OK <base>` が出たら `<base>` を戻り先として記録し:

```bash
git branch -d vibe/temp-feature 2>/dev/null; git checkout -b vibe/temp-feature
```

続けて `git rev-parse HEAD` を実行し、`<start_commit>` として記録する。

---

## Phase A: 要件定義 & スコープ縮退（planner）

次のように入力を標準入力で渡して（引用符や `$` を含むペインも変えずに渡すため。入力が空なら2行目を空にする。ペインに `SPEC_CYCLE_PAIN_EOF` だけの行があれば、終端の語を別の語に変える）、

```bash
python3 .claude/skills/spec-cycle/brief.py planner <<'SPEC_CYCLE_PAIN_EOF'
<入力をそのまま>
SPEC_CYCLE_PAIN_EOF
```

その出力を prompt として、Agent ツールで `planner` サブエージェントを起動する。planner は `agent-a.md` と以下のルールに従って `spec.json`（Cycle 1 は `.gitignore` も）を書き、検証まで済ませて報告する。

- **初回（spec.json なし、入力 = ペイン）:** `cycle_type: "cycle_1_tracer"`。ペインから過剰仕様を削除し、Tracer Bullet を1本だけ定義する。`current_baseline` は `{"test_status": "initial", "features": []}`。あわせて以下を行う:
  - ペインを解く最小の言語・実行環境を決め、`runtime` に記録する。外部依存は `runtime.dependencies` に列挙したものだけが許可される。
  - `runtime.test_command` は個々のテスト名と結果を1件ずつ出力する形にする（例: `python3 -m unittest -v`、`npx vitest run --reporter=verbose`）。sentry が Red で追加したテストの実行を確認するのに使う。
  - テストの実行方法を決めるファイル（マニフェスト、lockfile、テストランナー設定、conftest 等）を `runtime.harness_files` に列挙する。これらは Red でコミットした後、Green で変更できない。
  - `runtime.setup_command` は lockfile どおりに再現するコマンド（例: `npm ci`）にする。依存の新規導入には使わない。
  - `runtime` のコマンドはどれも単一のコマンドにする（`;` `&&` `|` リダイレクト等でつながない）。`.claude/settings.json` の `permissions.allow` にすでに一致するコマンドがあれば、それを選ぶ。許可されていないコマンドは `gate.py verify-commands` で止まり、人間が許可を追記してから再実行することになる。
  - その runtime がテスト実行時に生成するキャッシュ・成果物（例: Python の `__pycache__/`、Node の `node_modules/`、カバレッジ出力）を `.gitignore` に追記する。これを怠ると次サイクルの Step 0 が dirty で停止する。
- **拡張（spec.json あり、入力なし）:** `cycle_type: "cycle_n_expansion"`。`current_baseline` を保持したまま、`next_sprint_backlog` の先頭1件だけを `target_increment` に昇格させる。
- **拡張 + 新ペイン（spec.json あり、入力あり）:** ペインを縮退させて `next_sprint_backlog` に優先度順で差し込み、その先頭1件を昇格させる。既存の `current_baseline` と `wont` は壊さない。

出力ルール:

- `status` は `"ready_for_implementation"`。
- **作るものはすべてペインの原文に根拠を持つ。** 入力のペインは `pains` に一字一句そのまま追記する（既存の項目は変更しない）。`target_increment.source` と `next_sprint_backlog[].source` は、`pains` のどれかの部分文字列をそのまま引用する。ペインに書かれていない思いつきは backlog に入れず、`proposals` に記録するだけにする（人間が次のペインとして渡せば採用される）。
- **一度使った一節は使い回さない。** 完了済みの機能の `source` と重なる一節（一方が他方を含む）は、新しい増分にも backlog にも引用できない。ペイン全体を引用し直して続きを作ることはできず、続きには新しいペインが要る。backlog の項目同士も、別々の一節を引用する。
- **`execution_steps` には実装方法を書かない。** `assertion` はテストが観測すること（入力と期待値）だけ、`scope` は触ってよいファイルのパスをカンマ区切りで並べるだけにする。
- `target_increment` の関心事は **1つだけ**。複数混在していたら削ぎ落とし、残りを `next_sprint_backlog` へ。
- `wont` に該当する要望は昇格させない。`wont` の各項目には、人がペインに書きそうな短い `keyword`（例: GUI、pandas）を付ける。例外は、新ペインがその `keyword` を含んで解除を求めた場合だけ。そのときはその項目を `wont` から外し、`next_sprint_backlog` に入れる。
- 昇格させる前に、その項目が今の実装ですでに満たされていないか、実際にコードを動かして確かめる。満たされていれば Red のテストが最初から通り、3回差し戻されてロールバックになるため、昇格させずに `dropped_backlog` へ移す（`reason` と、確かめたコマンドと出力を `evidence` に書く）。次の項目で同じ確認を繰り返す。
- 新しいインターフェースの `then` は、宣言した出力の型の空の値（0、空リスト、空文字列、None、空のファイル）にしない。Red の空実装がその値を返すので、テストが最初から通ってしまう。ペインの例がちょうど空の値なら、空でない例を先に作り、空の場合は backlog に回す。
- ペインに書かれていない事実（入力形式・正解の値・業務ルールなど）は、人に質問せず最も一般的で単純な仮定で埋め、`assumptions` に追記する。既存の仮定と矛盾する新ペインが来たら、その仮定を書き換える。
- `runtime` は Cycle 1 で決めたら以降のサイクルでは変更しない。例外は `dependencies` だけで、`target_increment` が標準ライブラリと既存の依存では実現できない場合に限り、1サイクル1件まで追記できる（「パッケージ名 — 追加したサイクルと理由」の形。その依存に必要な `harness_files` の追記も同時に行う）。

planner の報告を受けたら、まず planner がコミットしておらず、`spec.json` と `.gitignore` 以外を触っていないことを確かめる（`HALT` ならロールバック。ゲート: planner）:

```bash
python3 .claude/skills/spec-cycle/gate.py verify-planner --expect <start_commit>
```

次にオーケストレーター自身が仕様を検証する。`--against HEAD` で前回の `spec.json` からの不変条件（`runtime` の固定、`pains` / `features` / `dropped_backlog` は追記のみ、依存とペインの追加は1件まで、`wont` はペインが名指ししたときだけ外せる、backlog の項目は `dropped_backlog` を経由してしか消えない）も確かめる。エラーなら同じ brief で planner を再起動する（3回失敗したらロールバック。ゲート: spec）:

```bash
python3 .claude/skills/spec-cycle/check_spec.py spec.json --against HEAD
```

次に、`runtime` のコマンドを人間が許可済みか確かめる。`gate.py` はこれらのコマンドを許可確認なしで実行するため、許可リストに一致しないコマンドは実行しない（`HALT` ならロールバック。ゲート: permission。出力された行を人間が `.claude/settings.json` に追記すれば、次の実行で通る）:

```bash
python3 .claude/skills/spec-cycle/gate.py verify-commands
```

検証を通ったら、仕様だけを先にコミットする（`git add` するのは実在するファイルだけ）:

```bash
git add spec.json .gitignore && git commit -m "spec: <feature_name> (<cycle_type>)"
```

コミット後に `git rev-parse HEAD` を実行し、`<spec_commit>` として記録する。続けて `python3 .claude/skills/spec-cycle/gate.py verify-clean` で、コミットから漏れたファイルがないことを確かめる（`HALT` ならロールバック）。

---

## Phase B: 設計 & 自律実装

### B-0: 現状確認

```bash
python3 .claude/skills/spec-cycle/gate.py baseline
```

Cycle 2 以降、`runtime.setup_command` を実行して作業ツリーが変わらないこと（lockfile 等が書き換わらないこと）と、既存テストがすべて通ることを確かめる。Cycle 1 は何もしない。`HALT` なら実装を始めずロールバックへ。

### B-1: 契約テスト（Red）→ コミット

`python3 .claude/skills/spec-cycle/brief.py builder-red` の出力を prompt として、Agent ツールで `builder` サブエージェントを起動する。builder は `builder.md` の Red モードに従う（要点: `given` の入力で `then` をそのまま assert するテストを書き、読み込みエラーでも呼び出し時のエラーでも未実装例外でもなく、assert で失敗させる。新しいインターフェースは、宣言した型の空の値（空リスト・0・空文字列・None など）を返し、テストが観測する副作用も空の形で起こす（例: 空のファイルを作る）だけの空実装にする。最初に失敗する assert は `then` を確かめるものでなければならず、空実装が先に落とす前提条件の assert（存在チェックなど）を前に置かない。既存の関数は本体に触れず、必要なら既定値付きの引数をシグネチャに足すだけ。テストがファイルを書くときは一時ディレクトリにだけ書く）。

Red の判定は sentry を呼ばず、`gate.py` だけで機械的に行う。builder が報告したテストの関数名（`Tests added`）で、HEAD が動いていないこと、各テストが今回追加されたものであること、`setup_command` で依存を入れ直してから再実行し、終了コードが 0 以外で各テストが assert の失敗として（例外による ERROR は不可）出力にあることを確かめる:

```bash
python3 .claude/skills/spec-cycle/gate.py verify-head --expect <spec_commit>
python3 .claude/skills/spec-cycle/gate.py verify-evidence --phase red --since <spec_commit> <builder が報告したテストの関数名...>
```

- `verify-head` が `HALT` なら、builder が履歴を書き換えたとみなしてロールバック。
- `verify-evidence` が `HALT evidence:` なら RETRY 扱い（試行回数 < 3）。builder-red の brief の末尾にその1行**だけ**を追記して builder を再起動し、上の2つを再実行する。3回目の `HALT evidence:`、またはそれ以外の `HALT`（permission / setup / security）ならロールバック（ゲート: evidence など、出力された語）。

`OK` なら、テストとハーネスをコミットしてロックする:

```bash
git add -u && git add <builder が新規作成したファイル...>
git commit -m "test(spec-cycle): red — <feature_name>"
```

コミット後に `git rev-parse HEAD` を実行し、`<red_commit>` として記録する。続けて `python3 .claude/skills/spec-cycle/gate.py verify-clean` を実行する（`HALT` ならロールバック）。builder が報告し忘れたテストがコミットから漏れると、固定されないまま Green で書き換えられるため。builder はこのコミットを書き換えられない（`guard-bash.py` が作業用ブランチ上での `git commit --amend` / `git reset` / `git rebase` をブロックし、sentry の前に `verify-head` でハッシュを照合する）。テストが `then` をそのまま確かめているか、既存のテストや `spec.json` を改ざんしていないかは、B-2 の sentry が Red のコミットも含めて判定する。

### B-2: 最小実装（Green）→ sentry

`python3 .claude/skills/spec-cycle/brief.py builder-green` の出力を prompt として、`builder` を起動する。builder は `builder.md` の Green モードに従う（要点: コミット済みのテストとハーネスを変えずに、テストを通す最小のコードを書き、報告の前に整形する。テストが誤っていると判断したら Concerns に書く）。

続けて sentry を呼ぶ（このサイクルで sentry を呼ぶのはここだけ）:

1. 起動する前に、HEAD が `<red_commit>` で `vibe/temp-feature` 上にいることを確かめ、作業ツリーのハッシュを記録する。`HALT` なら builder が履歴を書き換えたとみなしてロールバック:

   ```bash
   python3 .claude/skills/spec-cycle/gate.py verify-head --expect <red_commit>
   python3 .claude/skills/spec-cycle/gate.py snapshot        # 出力を <snapshot> として記録
   ```

2. `python3 .claude/skills/spec-cycle/brief.py sentry --iteration <n> --base <red_commit>` の出力を prompt として、Agent ツールで `sentry` サブエージェントを起動する。sentry は spec.json を自分で読み、テスト実行と、Red と Green を合わせた差分の機械的レビューを行い、`SHIP | RETRY | HALT` と根拠（テスト結果の要約行と、Red で追加したテストの名前）を返す。別のレビュアーエージェントは使わない。

3. sentry は読み取り専用。終了後に作業ツリーが変わっていないことを確かめる（`HALT` ならロールバック）:

   ```bash
   python3 .claude/skills/spec-cycle/gate.py verify-unchanged --snapshot <snapshot>
   ```

4. SHIP なら、sentry が根拠に挙げたテストの関数名（`test_total` のような名前だけ。クラス名や括弧は付けない）で裏を取る。各テストが Red のコミットに含まれることを確かめたうえで、`setup_command` で依存を入れ直してからテストを再実行し、終了コードが 0 で各テストが成功として出力にあることを確かめる（`HALT` ならロールバック。ゲート: evidence）:

   ```bash
   python3 .claude/skills/spec-cycle/gate.py verify-evidence --phase green --since <spec_commit> --until <red_commit> <テストの関数名...>
   ```

判定の扱い（試行回数は 1 から数える）:

- **SHIP:** 裏を取ってから B-3 へ。
- **RETRY（試行回数 < 3）:** builder-green の brief の末尾に、sentry の Issues（最大3行）と、あれば失敗ログ（先頭30行）**だけ** を追記して builder を再起動し、sentry を再実行する。
- **RETRY が3回目 または HALT（セキュリティ欠陥と、ロック済みの Red の欠陥は即時）:** 「ロールバック」へ。

### ロールバック

失敗した仕様とテストを後から追えるよう、ブランチの先端をタグで残してから戻す。タグ名はコマンド置換を使わず、先に `date +%Y%m%d-%H%M%S` を実行して得た値をそのまま書く:

```bash
git tag vibe/failed/<timestamp> vibe/temp-feature
git checkout -f <base> && git branch -D vibe/temp-feature && git clean -fd
```

2行目は `guard-bash.py` がこの形のときだけ通す。後ろに別のコマンドをつながない。この2行は `test_rollback.py` がそのまま抜き出して実行・検証しているので、書き換えたらテストを実行する。

以下を出力して停止する:

- `[FATAL] spec-cycle halted (<phase>/<gate>, attempt <n>/3). Rolled back to <base>. Spec kept at vibe/failed/<timestamp>.`
- ゲートが `permission` なら、`gate.py verify-commands` が出力した行（人間が `.claude/settings.json` の `permissions.allow` に追記するもの）。パイプラインは追記しない
- 最終試行の Issues と失敗ログ
- builder が報告した Concerns（あれば）。テストや仕様の誤りが原因なら、人間が新しいペインで直せる
- 仕様は `git show vibe/failed/<timestamp>:spec.json` で参照できること。調べ終えたタグは人間が `git tag -d vibe/failed/<timestamp>` で消してよい

### B-3: spec.json 自律更新 & コミット

全 Green を確認したら `spec.json` を更新する:

- `status`: `"completed"`
- `current_baseline.test_status`: `"all_green"`
- `current_baseline.features`: 今回の機能を1件 **追記** する。既存の項目は変更・削除しない。形は次のとおり（`interface` は文字列ではなく `input` / `output` を持つオブジェクト）:

  ```json
  {"name": "<feature_name>", "source": "<今回の target_increment.source をそのまま>", "file": "<実装のファイルパス>", "symbol": "<関数名・クラス名>",
   "interface": {"input": "<引数と型>", "output": "<戻り値の型と副作用>"}}
  ```
- `target_increment`: 各フィールドを空文字（`acceptance_criteria` は空の given/when/then）にクリア
- `execution_steps`: 空配列にする（前サイクルの手順を残さない）
- `pains` / `assumptions` / `wont` / `dropped_backlog` / `proposals`: そのまま残す
- `next_sprint_backlog`: 今回完了した項目を削除し、残りは順序を維持

`python3 .claude/skills/spec-cycle/gate.py verify-head --expect <red_commit>` と `python3 .claude/skills/spec-cycle/check_spec.py spec.json --against HEAD` が通ること（`file` の実在と `symbol` の存在、`features` がちょうど1件増えたこと、その `source` が今回の増分のものであることも検証される）を確認してからコミットする（`git add .` は禁止。新規ファイルは builder の報告したパスを明示指定する）:

```bash
git add -u && git add <builder が新規作成したファイル...>
git commit -m "feat(spec-cycle): <feature_name> [auto-verified]"
```

`.env*` が staging に含まれていないことを `git diff --cached --name-only` で確認してからコミットし、コミット後に `python3 .claude/skills/spec-cycle/gate.py verify-clean` で、実装がコミットから漏れていないことを確かめる（`HALT` なら、漏れたファイルを追加するコミットを重ねて再確認する。2回続けて `HALT` ならロールバック）。ハーネスがコミットの署名行（`Co-Authored-By:` 等）を指定している場合は、このスキルのすべてのコミット（spec / red / feat）に付ける。

---

## 完了レポート

以下だけを出力して終了する:

1. ブランチ: `vibe/temp-feature`（マージは人間が動作確認後に行う）
2. 今回の Increment: `feature_name` / `focus` と、その根拠となるペインの一節（`target_increment.source`）
3. 作成・通過したテスト（Red はゲートの確認、Green は sentry の根拠とオーケストレーターの裏取りの結果）
4. 変更ファイルとコミットハッシュ（spec / red / feat の3つ）
5. 今回置いた仮定: 今サイクルで `assumptions` に追加・変更した項目（外れていれば新しいペインとして渡せば次サイクルで直る）
6. 今回追加した依存（あれば）: `runtime.dependencies` に追記した項目
   - backlog から外した項目（あれば）: `dropped_backlog` に追記した項目と、その理由・根拠
7. 次スプリント候補: `next_sprint_backlog` の先頭
8. 提案（あれば）: `proposals` に記録された、ペインに根拠がないため作らない案。採用するなら人間がペインとして渡す
9. 次の一手: `vibe/temp-feature` を <base> にマージ → `next_sprint_backlog` が残っていれば引数なしで `/spec-cycle`、空なら新しいペインを付けて `/spec-cycle "<ペイン>"` を実行（空のまま引数なしで実行すると Step 0 で止まる）

## 禁止事項

- `main` 上での直接実装（必ず `vibe/temp-feature`）
- テストが Red のまま終了すること
- Red でコミットしたテスト・ハーネスを Green で変更すること
- `.claude/` 配下の変更（権限の自己付与を含む）
- `wont` 記載項目の実装
- ペインに根拠のない項目を `target_increment` や `next_sprint_backlog` に入れること
- サブエージェントへの prompt に `brief.py` の出力以外を書き足すこと（RETRY 時のゲートの1行、Issues、失敗ログを除く）
- 人間への質問（Step 0 の停止条件を除く）
