# leanshift-trend-bot — LangGraph移行設計書

作成日: 2026-08-14

## 背景・目的

現行の `leanshift-trend-bot` は `fetcher.py → analyzer.py → main.py` の単純な線形パイプライン（4ソース取得 → 12記事を1回のGeminiバッチ呼び出しで一括分析 → Markdown保存）である。

本設計の目的は以下の2点：

1. **LangGraphへの移行**: 単純なバッチ処理から、記事ごとのfan-out並列処理・自己評価による生成ループ（Loop Engineering）・チェックポイントによる再開性を備えた、実務レベルのLangGraphアプリケーションへ作り変える。
2. **フレームワーク非依存な設計**: 将来LangGraphから他のフレームワーク（CrewAI等）やAIエージェント実装に移行する際、ドメインロジックを一切変更せずにオーケストレーション層だけ差し替えられるディレクトリ構成にする。

**背景**: 本プロジェクトはFDE（Forward Deployed Engineer）案件獲得のためのポートフォリオ実績として使う想定。LangGraphはFDE業務のデファクトスタンダードであり、Send APIによるfan-out/fan-in、条件付きエッジによるループ（Loop Engineering）、チェックポイントによる永続化・再開性など、代表的なLangGraphパターンを実装で示すことに重きを置く。

## 1. 全体アーキテクチャ方針

**ports-and-adapters（core / orchestration 分離）** を採用する。

- `core/` — フレームワーク非依存のドメインロジック（fetch・prompt構築・パース・評価・ランキング・レポート生成）。LangGraph SDKに依存しない
- `orchestration/langgraph_app/` — LangGraph固有のグラフ定義・ノード・State・checkpointer。`core/` の関数を呼び出すだけの薄いアダプタ層

将来別フレームワークに移行する場合は `orchestration/<別フレームワーク>_app/` を追加するだけでよく、`core/` は変更不要とする。Protocol/ABC等の抽象化レイヤーは導入しない（YAGNI。過剰な抽象化を避ける）。

`models.py` は変更不可のマスターであるため、パス・内容ともにルート直下のまま維持し、`core/` からは `from models import ...` で参照する。旧 `ProcessedDraft`（後方互換用・非推奨コメント付き）は使わず、既存の `AnalysisCore` / `XDraft` / `ZennDraft` / `ProcessedArticle` を正式採用し、models.py内のコメントが示す移行を完了させる。

## 2. ディレクトリ構成

```
leanshift-trend-bot/
├── models.py                          # 【不変】既存のまま
├── main.py                            # CLIエントリーポイント（await graph.ainvoke() + コンソール出力）
├── langgraph.json                     # LangGraph CLI/Studio 用設定
├── my_status.txt
│
├── core/                              # フレームワーク非依存ドメインロジック
│   ├── sources/                       # 旧 fetcher.py を分割
│   │   ├── base.py                    #   共通の _strip_html 等
│   │   ├── hackernews.py
│   │   ├── producthunt.py
│   │   ├── techcrunch.py
│   │   └── reddit.py
│   ├── analysis/                      # 旧 analyzer.py を分割
│   │   ├── schemas.py                 #   LLM構造化出力用の中間スキーマ（models.py外、ScoredDraft含む）
│   │   ├── client.py                  #   _build_client（Gemini接続・リトライ設定）
│   │   ├── prompts.py                 #   生成用・評価用システムプロンプト
│   │   ├── generate.py                #   記事1件の分析生成
│   │   ├── evaluate.py                #   生成物の自己評価（quality gate、pass/fail+feedback）
│   │   └── parsing.py                 #   レスポンス→Pydanticマッピング（pytest対象）
│   ├── ranking.py                     #   fan-in後の重み付けソート（LLM不要、pytest対象）
│   └── reporting.py                   #   Markdownレポート生成（旧 main.py の save_markdown_report）
│
├── orchestration/
│   └── langgraph_app/                 # LangGraph固有実装（将来 crewai_app/ 等が並ぶ想定）
│       ├── state.py                   #   GraphState / ArticleState（TypedDict）
│       ├── subgraphs/
│       │   └── article_analysis.py    #   記事1件用サブグラフ：generate→evaluate→(loop/END)
│       ├── nodes/
│       │   ├── fetch_nodes.py         #   4ソース並列fetchノード
│       │   ├── dispatch.py            #   Send APIでarticle_analysisへfan-out
│       │   ├── rank_node.py           #   fan-in後のランキングノード
│       │   └── report_node.py         #   レポート保存ノード（core/reporting.pyを呼ぶだけ、ファイルI/Oのみ）
│       ├── graph.py                   #   StateGraph組み立て（checkpointer差し替え可能なfactory関数、compile済みgraphをexport）
│       └── checkpointer.py            #   AsyncSqliteSaver設定（WALモード）
│
├── tests/
│   ├── core/
│   │   ├── test_parsing.py            #   旧 test_analyzer.py 相当
│   │   ├── test_evaluate.py           #   評価ロジック（新規）
│   │   └── test_ranking.py            #   重み付けソート（新規）
│   └── __init__.py
│
└── docs/…（既存 + 本設計書）
```

旧 `fetcher.py` / `analyzer.py` / 旧 `main.py` のロジックはこの構成に移設し、元ファイルは削除する。

## 3. グラフフロー & State設計

```
START
  │
  ├─► fetch_hn ──┐
  ├─► fetch_ph ──┤ (並列fan-out)
  ├─► fetch_tc ──┤
  └─► fetch_reddit┘
        │ (fan-in: articles: Annotated[list[RawArticle], merge_by_url])
        ▼
   dispatch (Send APIで記事ごとにarticle_analysisサブグラフへfan-out)
        │
        ├─► article_analysis[article_1] ─┐
        ├─► article_analysis[article_2] ─┤
        ├─► ...                          ┤ (12件並列実行、各々が下記サイクルを内包)
        └─► article_analysis[article_12]─┘
        │ (fan-in: scored: Annotated[list[ScoredDraft], merge_by_article_id])
        ▼
   rank_node（Pythonで重み付けスコア計算→ソート→AnalysisCore.rankを確定）
        │
        ▼
   report_node（Markdown保存のみ、ファイルI/O）
        │
        ▼
       END
        │
        ▼ (graph.ainvoke() の戻り値を受け取って)
   main.py がコンソール出力を行う
```

**カスタムreducer（`merge_by_url` / `merge_by_article_id`）:** 単純な `operator.add` は再実行・リトライ時に同じ記事が重複追加される問題があるため（LangGraph公式ドキュメント「Re-execution and idempotency」原則: ノード再実行が状態を壊さないよう設計すべき、に準拠）、`url` / `article_id` をキーに既存リストとマージし重複を排除するカスタムreducer関数を `orchestration/langgraph_app/state.py` に定義し、`Annotated` に適用する。

### article_analysis サブグラフ（1記事内で完結するループ）

```
   generate ──► evaluate ──[fail & iteration<MAX]──► generate（フィードバック付き再生成）
                   │
                [pass or iteration>=MAX]
                   ▼
                  END（親グラフへ ScoredDraft を返す）
```

`evaluate` ノードは、機械的チェック（x_post文字数100〜130字、viral_score範囲1〜5等）とLLMによる自己評価（構造化出力で `{pass: bool, feedback: str}`）を組み合わせて判定する。`MAX_ITERATIONS = 3`（初回生成＋最大2回の再生成）とし、コスト・レイテンシとのバランスを取る。反復上限に達した場合はfail扱いのまま次工程に進める（パイプライン全体は止めない）。

**`ArticleState`（サブグラフ内のみで使うState）:**

```python
class ArticleState(TypedDict):
    article: RawArticle
    user_status: str
    draft: ScoredDraft | None
    feedback: str | None      # evaluate が fail 判定時に書き込む差し戻し理由
    iteration: int             # 現在の反復回数（0始まり）
```

`generate` ノードはプロンプト構築時に `feedback` が `None` でなければ「前回の指摘: {feedback}」を追加挿入して再生成する。`evaluate` は判定後に `feedback` と `iteration + 1` を返し、条件付きエッジがこの2値を見て `generate` に戻すか `END` に進むかを決定する。

### models.py制約への対応（重要な設計判断）

現行の一括バッチでは記事間の相対比較で `rank` をLLMが直接決めていたが、記事ごとにfan-outすると相対比較ができない。`AnalysisCore` には関心度/ビジネス価値/新規性の軸別スコアを格納するフィールドがなく、`models.py` は変更不可のため、既存の `_RankedArticleJSON` パターン（models.py外の中間スキーマ）を踏襲し、`core/analysis/schemas.py` に **`ScoredDraft`**（`ProcessedArticle` + `interest_score` / `business_value_score` / `novelty_score`）を定義する。

サブグラフはこの `ScoredDraft` を返し、`rank_node` が軸別スコアから重み付け合計（関心度×0.5 + ビジネス価値×0.3 + 新規性×0.2、既存の `ranking_logic_design.md` の式を踏襲）を計算してソートし、最終的な `AnalysisCore.rank` を確定した `ProcessedArticle` のリストに変換する。軸別スコア自体は最終出力（レポート）には残さない。

## 4. エラーハンドリング・チェックポイント・テスト戦略

### エラーハンドリング

- Gemini呼び出しは既存の `HttpRetryOptions`（5回・指数バックオフ）を `core/analysis/client.py` にそのまま継承する。
- `article_analysis` サブグラフ内で1記事が最終的に失敗した場合、パイプライン全体は止めずエラー情報付きでスキップし、レポートに「12件中N件成功」を明記する（1記事の失敗が他11記事を巻き込まない設計）。
- 12記事を同時にGemini APIへ送るとレート制限（429）に当たるリスクがあるため、`graph.ainvoke()` 呼び出し時に `config={"max_concurrency": N}`（例: N=5）を指定し、同時実行数を制御する。既存のリトライ設定と合わせて二重に保険をかける。

### チェックポイント

- Send APIによる12記事の並列fan-outを活かすため、グラフは非同期（`graph.ainvoke()` / `astream()`）で実行する。LangGraph公式ドキュメントは非同期実行時は同期版 `SqliteSaver` ではなく **`AsyncSqliteSaver`** を使うよう明記しているため、`AsyncSqliteSaver`（`checkpoints.sqlite`、`.gitignore` 対象、`PRAGMA journal_mode=WAL` を有効化）を採用する。
- `thread_id` は実行日付ベース（例: `run-2026-08-14`）とし、同日再実行時は続きから再開可能にする。
- `main.py` はCLIのまま、`config={"configurable": {"thread_id": ...}, "max_concurrency": N}` を渡して `await graph.ainvoke(...)` する。
- 本番運用でさらなる高負荷が想定される場合は `AsyncPostgresSaver` への切り替えをスコープ外の将来拡張として記載する（公式ドキュメントもPostgresを本番向けに推奨）。

### LangGraph Studio対応

- `langgraph.json` を追加し、`orchestration.langgraph_app.graph:graph` をエントリーとして公開する。`langgraph dev` でグラフを可視化・デバッグできるようにする。
- `graph.py` は `build_graph(checkpointer: BaseCheckpointSaver | None = None)` のfactory関数として実装し、CLI実行時は `AsyncSqliteSaver` を明示的に渡す一方、Studio用に `langgraph.json` が参照するモジュールレベル変数 `graph` はcheckpointer未指定（`langgraph dev` のローカル開発用チェックポインタに委ねる）でcompileする。

### テスト戦略（CLAUDE.md 憲法②に準拠）

- `core/analysis/parsing.py`（レスポンス→Pydanticマッピング）… pytest必須
- `core/analysis/evaluate.py`（quality gate判定ロジック）… pytest必須（新規の複雑ロジックのため）
- `core/ranking.py`（重み付けソート）… pytest必須（新規の複雑ロジックのため）
- `core/sources/*`（外部I/O）… テスト不要（既存方針通り）
- LangGraphのグラフ配線自体（`graph.py`）… 単体テスト不要。動作確認は `verify` スキルで実グラフを動かして確認する
- 完了報告前に必ず `mypy .` を実行し型エラー0件を確認する（CLAUDE.md 憲法①）

### 依存関係の追加

- `langgraph`、`langgraph-checkpoint-sqlite` を `requirements.txt` に追加する。
- 既存コードが依存しているにもかかわらず未記載だった `google-genai` も併せて追加する。

## スコープ外（将来拡張として残す）

- Human-in-the-loop（公開前の人間承認、`interrupt()` による差し戻しフロー）は今回実装しない。
- 音楽・投資・X等の新規データソース追加は今回実装しない（ただし `core/sources/` の構成はソース追加を前提に設計している）。
- `AsyncPostgresSaver` への切り替え（本番相当のスケール・同時実行数が必要になった場合）。

## 改訂履歴

- 2026-08-14: 初版作成。
- 2026-08-14: レビュー指摘を反映し改訂。`SqliteSaver`→`AsyncSqliteSaver`（非同期実行前提、公式ドキュメントの推奨に準拠）、`operator.add`→URL/article_idキーのカスタムreducer（重複防止）、`ArticleState` のfeedback/iterationフィールドを明記、`report_node` をファイルI/O専任に変更しコンソール出力は `main.py` に分離、Studio用にcheckpointer差し替え可能なfactory構成に変更、`max_concurrency` によるレート制限対策を追加。
