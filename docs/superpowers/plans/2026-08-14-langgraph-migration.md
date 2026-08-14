# leanshift-trend-bot LangGraph移行 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 現行の線形パイプライン(`fetcher.py → analyzer.py → main.py`)を、core/orchestration分離・Send APIによる記事ごとのfan-out・自己評価ループ(Loop Engineering)・AsyncSqliteSaverチェックポイントを備えたLangGraphアプリケーションに作り変える。

**Architecture:** `core/`(フレームワーク非依存のドメインロジック)と`orchestration/langgraph_app/`(LangGraph固有のグラフ・ノード・State)を分離するports-and-adapters構成。`models.py`は変更不可のため、LLM構造化出力用の中間スキーマ(`ScoredDraft`等)は`core/analysis/schemas.py`に定義する。

**Tech Stack:** Python 3.10, Pydantic v2, LangGraph, `langgraph-checkpoint-sqlite`(AsyncSqliteSaver), google-genai(Gemini 2.5 Flash Lite), pytest, mypy。

**設計書:** `docs/superpowers/specs/2026-08-14-langgraph-migration-design.md`(必ず先に読むこと)

## Global Constraints

- `models.py` の `RawArticle` / `AnalysisCore` / `XDraft` / `ZennDraft` / `ProcessedArticle` の定義は一切変更しない(CLAUDE.md 憲法)。
- 各タスク完了報告前に必ず `python3 -m mypy .` を実行し型エラー0件を確認する(CLAUDE.md 憲法①)。
- `RawArticle → ProcessedDraft相当` のパースロジックや評価・ランキングなど複雑なロジックには必ずpytestを書く。`core/sources/*`(外部I/O)、`core/analysis/client.py`・`prompts.py`(定数のみ)、`core/reporting.py`(単純な整形)、およびLangGraphのグラフ配線自体は対象外(CLAUDE.md 憲法②)。
- 非同期実行(`ainvoke`)を前提とする。同期版`SqliteSaver`ではなく`AsyncSqliteSaver`を使う。
- コミットは各タスクの最後にまとめて1回行う。コミットメッセージ末尾に `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` は不要(このプロジェクトの既存コミット規約に合わせ通常のメッセージのみでよい)。

---

### Task 1: 依存関係とパッケージスケルトン

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Create: `core/__init__.py`, `core/sources/__init__.py`, `core/analysis/__init__.py`
- Create: `orchestration/__init__.py`, `orchestration/langgraph_app/__init__.py`, `orchestration/langgraph_app/subgraphs/__init__.py`, `orchestration/langgraph_app/nodes/__init__.py`
- Create: `tests/core/__init__.py`, `tests/orchestration/__init__.py`

**Interfaces:**
- Produces: `core`, `core.sources`, `core.analysis`, `orchestration`, `orchestration.langgraph_app`, `orchestration.langgraph_app.subgraphs`, `orchestration.langgraph_app.nodes` が import 可能なパッケージとして存在する。

- [ ] **Step 1: requirements.txt に google-genai を追加**

`requirements.txt` を以下に置き換える(既存コードが依存しているのに未記載だったため追加):

```
anthropic>=0.109.1
feedparser>=6.0.12
pydantic>=2.12.5
python-dotenv>=1.2.1
google-genai>=2.8.0
```

- [ ] **Step 2: langgraph と langgraph-checkpoint-sqlite をインストール**

Run: `pip install langgraph langgraph-checkpoint-sqlite`
Expected: インストール成功(バージョン番号はその時点の最新でよい)

- [ ] **Step 3: インストールされたバージョンを requirements.txt に追記**

Run: `pip show langgraph langgraph-checkpoint-sqlite | grep -E "^(Name|Version)"`

出力された正確なバージョン番号を使い、`requirements.txt` の末尾に以下の2行を追記する(`X.Y.Z` は実際のコマンド出力の値に置き換えること):

```
langgraph>=X.Y.Z
langgraph-checkpoint-sqlite>=X.Y.Z
```

- [ ] **Step 4: .gitignore にチェックポイントDBを追加**

`.gitignore` を以下に置き換える:

```
.env
__pycache__/
checkpoints.sqlite*
```

- [ ] **Step 5: パッケージディレクトリとテストディレクトリを作成**

Run:
```bash
mkdir -p core/sources core/analysis
mkdir -p orchestration/langgraph_app/subgraphs orchestration/langgraph_app/nodes
mkdir -p tests/core tests/orchestration
touch core/__init__.py core/sources/__init__.py core/analysis/__init__.py
touch orchestration/__init__.py orchestration/langgraph_app/__init__.py
touch orchestration/langgraph_app/subgraphs/__init__.py orchestration/langgraph_app/nodes/__init__.py
touch tests/core/__init__.py tests/orchestration/__init__.py
```

- [ ] **Step 6: インポート疎通確認**

Run: `python3 -c "import core, core.sources, core.analysis, orchestration, orchestration.langgraph_app; from langgraph.graph import StateGraph, START, END; from langgraph.types import Send; from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver; print('ok')"`
Expected: `ok` が出力される(エラーなし)

- [ ] **Step 7: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found` (空パッケージのみのため既存コードに影響なし)

- [ ] **Step 8: コミット**

```bash
git add requirements.txt .gitignore core orchestration tests/core tests/orchestration
git commit -m "chore: LangGraph移行用の依存関係とパッケージスケルトンを追加"
```

---

### Task 2: RSSソース取得ロジックを core/sources/ へ移設

**Files:**
- Create: `core/sources/base.py`
- Create: `core/sources/hackernews.py`
- Create: `core/sources/producthunt.py`
- Create: `core/sources/techcrunch.py`
- Create: `core/sources/reddit.py`
- Delete: `fetcher.py`

**Interfaces:**
- Produces: `core.sources.hackernews.fetch_hn_articles(limit: int = 3) -> list[RawArticle]`, `core.sources.producthunt.fetch_product_hunt_articles(limit: int = 3) -> list[RawArticle]`, `core.sources.techcrunch.fetch_techcrunch_articles(limit: int = 3) -> list[RawArticle]`, `core.sources.reddit.fetch_reddit_articles(limit: int = 3) -> list[RawArticle]`

- [ ] **Step 1: core/sources/base.py を作成**

```python
import re

USER_AGENT = "Mozilla/5.0 (compatible; leanshift-trend-bot/1.0)"


def strip_html(text: str) -> str:
    """HTMLタグを除去してプレーンテキストにする"""
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean).strip()
```

- [ ] **Step 2: core/sources/hackernews.py を作成**

```python
import feedparser
from models import RawArticle

HNRSS_URL = "https://hnrss.org/frontpage?points=200"
FETCH_LIMIT = 3


def fetch_hn_articles(limit: int = FETCH_LIMIT) -> list[RawArticle]:
    feed = feedparser.parse(HNRSS_URL)
    articles: list[RawArticle] = []

    for entry in feed.entries[:limit]:
        summary = entry.get("summary", "") or entry.get("description", "")
        articles.append(
            RawArticle(
                source_name="Hacker News",
                category="Tech",
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                summary=summary,
            )
        )

    return articles
```

- [ ] **Step 3: core/sources/producthunt.py を作成**

```python
import feedparser
from models import RawArticle
from core.sources.base import strip_html

PRODUCTHUNT_RSS_URL = "https://www.producthunt.com/feed"
FETCH_LIMIT = 3


def fetch_product_hunt_articles(limit: int = FETCH_LIMIT) -> list[RawArticle]:
    feed = feedparser.parse(PRODUCTHUNT_RSS_URL)
    articles: list[RawArticle] = []

    for entry in feed.entries[:limit]:
        raw_summary = entry.get("summary", "") or entry.get("description", "")
        articles.append(
            RawArticle(
                source_name="Product Hunt",
                category="Tech",
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                summary=strip_html(str(raw_summary)),
            )
        )

    return articles
```

- [ ] **Step 4: core/sources/techcrunch.py を作成**

```python
import feedparser
from models import RawArticle
from core.sources.base import strip_html

TECHCRUNCH_STARTUPS_RSS_URL = "https://techcrunch.com/category/startups/feed/"
FETCH_LIMIT = 3


def fetch_techcrunch_articles(limit: int = FETCH_LIMIT) -> list[RawArticle]:
    feed = feedparser.parse(TECHCRUNCH_STARTUPS_RSS_URL)
    articles: list[RawArticle] = []

    for entry in feed.entries[:limit]:
        raw_summary = entry.get("summary", "") or entry.get("description", "")
        articles.append(
            RawArticle(
                source_name="TechCrunch",
                category="Startups",
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                summary=strip_html(str(raw_summary)),
            )
        )

    return articles
```

- [ ] **Step 5: core/sources/reddit.py を作成**

```python
import feedparser
from models import RawArticle
from core.sources.base import strip_html, USER_AGENT

REDDIT_WEBDEV_RSS_URL = "https://www.reddit.com/r/webdev/hot/.rss"
FETCH_LIMIT = 3


def fetch_reddit_articles(limit: int = FETCH_LIMIT) -> list[RawArticle]:
    feed = feedparser.parse(REDDIT_WEBDEV_RSS_URL, agent=USER_AGENT)
    articles: list[RawArticle] = []

    for entry in feed.entries[:limit]:
        raw_summary = entry.get("summary", "") or entry.get("description", "")
        articles.append(
            RawArticle(
                source_name="Reddit",
                category="r/webdev",
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                summary=strip_html(str(raw_summary)),
            )
        )

    return articles
```

- [ ] **Step 6: 旧 fetcher.py を削除**

Run: `git rm fetcher.py`

- [ ] **Step 7: インポート疎通確認**

Run: `python3 -c "from core.sources.hackernews import fetch_hn_articles; from core.sources.producthunt import fetch_product_hunt_articles; from core.sources.techcrunch import fetch_techcrunch_articles; from core.sources.reddit import fetch_reddit_articles; print('ok')"`
Expected: `ok`

- [ ] **Step 8: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`(`fetcher.py`削除により参照エラーが出る場合は他モジュールの旧インポートを確認・修正すること。ただしこの時点では他モジュールはまだ`fetcher.py`を参照していないはず)

- [ ] **Step 9: コミット**

```bash
git add core/sources fetcher.py
git commit -m "refactor: RSSソース取得ロジックをcore/sources/へ移設"
```

---

### Task 3: core/analysis/schemas.py — ScoredDraftとLLM構造化出力スキーマ

**Files:**
- Create: `core/analysis/schemas.py`

**Interfaces:**
- Consumes: `models.RawArticle`, `models.AnalysisCore`, `models.XDraft`, `models.ZennDraft`, `models.ProcessedArticle`
- Produces: `ScoredDraft`(フィールド: `raw: RawArticle`, `analysis: AnalysisCore`, `x: XDraft`, `zenn: ZennDraft`, `interest_score: int`, `business_value_score: int`, `novelty_score: int`)、`GeneratedAnalysisJSON`(Gemini生成ステップ用スキーマ)、`EvaluationJSON`(Gemini評価ステップ用スキーマ、フィールド `passed: bool`, `feedback: str`)

- [ ] **Step 1: core/analysis/schemas.py を作成**

```python
from pydantic import BaseModel
from models import RawArticle, AnalysisCore, XDraft, ZennDraft


class ScoredDraft(BaseModel):
    """1記事分の生成結果 + ランキング用の軸別スコア(models.py外の中間モデル)"""
    raw: RawArticle
    analysis: AnalysisCore
    x: XDraft
    zenn: ZennDraft
    interest_score: int
    business_value_score: int
    novelty_score: int


class GeneratedAnalysisJSON(BaseModel):
    """Geminiの生成ステップ用構造化出力スキーマ"""
    evaluation_reason: str
    interest_score: int
    business_value_score: int
    novelty_score: int
    viral_score: int
    improved_title: str
    summary: str
    business_idea: str
    x_post: str
    zenn_title: str
    zenn_sections: list[str]
    zenn_intro: str
    zenn_tags: list[str]


class EvaluationJSON(BaseModel):
    """Geminiの自己評価ステップ用構造化出力スキーマ"""
    passed: bool
    feedback: str
```

- [ ] **Step 2: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`

- [ ] **Step 3: コミット**

```bash
git add core/analysis/schemas.py
git commit -m "feat: ScoredDraftとLLM構造化出力スキーマを追加"
```

---

### Task 4: core/analysis/client.py と core/analysis/prompts.py

**Files:**
- Create: `core/analysis/client.py`
- Create: `core/analysis/prompts.py`

**Interfaces:**
- Produces: `core.analysis.client.build_client() -> genai.Client`, `core.analysis.client.MODEL: str`、`core.analysis.prompts.GENERATE_SYSTEM_PROMPT: str`、`core.analysis.prompts.EVALUATE_SYSTEM_PROMPT: str`

- [ ] **Step 1: core/analysis/client.py を作成**

```python
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = "models/gemini-2.5-flash-lite"


def build_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。")
    # google-genai はデフォルトでリトライ無効(1回失敗即エラー)のため、
    # 503(高負荷)等の一時的なエラーに備えて明示的に有効化する。
    retry_options = types.HttpRetryOptions(
        attempts=5,
        initial_delay=2.0,
        max_delay=30.0,
        exp_base=2.0,
        jitter=1.0,
    )
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(retry_options=retry_options),
    )
```

- [ ] **Step 2: core/analysis/prompts.py を作成**

```python
GENERATE_SYSTEM_PROMPT = (
    "あなたは海外テックトレンドを分析する優秀なリサーチスペシャリストです。\n"
    "与えられた1件の英語技術記事を分析し、ユーザーの関心事項に基づいてスコアリング・バズ度評価・"
    "日本語タイトル改善を行い、分析データを生成してください。\n\n"
    "# 1. スコアリング基準(1〜5点)\n"
    "- interest_score(ユーザー関心度): <user_interests> のキーワードと完全一致=5、周辺技術=3、無関係=1\n"
    "  ※セマンティック拡張を許可(Next.jsならReact/Vercel/SSRも関連とみなす)\n"
    "  ※ user_interests が提供されない場合は3を基準にする\n"
    "- business_value_score(ビジネス・技術価値): 産業変革レベル=5、便利な新ツール=3、個人ブログ記事=1\n"
    "- novelty_score(新規性): 初回ローンチ=5、メジャーアップデート=3、既存技術の解説=1\n\n"
    "# 2. バズ度スコア(viral_score)\n"
    "日本のテックコミュニティ(X・Zenn・はてなブックマーク)での拡散しやすさを1〜5の整数で評価:\n"
    "- 5: トレンド技術の重大発表、劇的な数値実績(100倍高速化など)\n"
    "- 4: 人気フレームワークのメジャーアップデート、著名スタートアップの巨額調達\n"
    "- 3: 実用的なOSSツールの紹介、ニッチだが有用なAI SaaS\n"
    "- 2: 標準的な技術チュートリアルや一般的な解説記事\n"
    "- 1: 特定領域すぎるニュース、話題性が極めて限定的\n\n"
    "# 3. 改善日本語タイトル(improved_title)\n"
    "30文字程度で以下のいずれかのパターンを必ず適用。元タイトルの直訳は絶対に避ける:\n"
    "- 数字の法則: 具体的な数値で凄さを伝える(例:「2万スター突破!Rust製Pythonツール」)\n"
    "- 対比の法則: 旧常識との対比で新パラダイムを示す(例:「まだXXで消耗してる?」)\n"
    "- 簡易の法則: 時短・初心者訴求で心理的障壁を下げる(例:「10分で作れる〇〇」)\n"
    "- 権威の法則: 著名ブランド・巨額調達で市場性を印象付ける\n"
    "- 探究の法則: 「なぜ〇〇なのか?」で知的好奇心を刺激する\n\n"
    "# 4. summary\n"
    "記事の本質と、なぜ海外で話題になっているかの背景を日本語3〜5文でまとめる。\n\n"
    "# 5. business_idea\n"
    "日本市場向けローカライズビジネスモデルを日本語で提案する。\n\n"
    "# 6. x_post\n"
    "絵文字1個+改行+本文1〜2文+末尾に{URL}プレースホルダー。URLを除いて100〜130文字。ハッシュタグ不要。\n\n"
    "# 7. Zenn記事構成案(zenn_title / zenn_sections / zenn_intro / zenn_tags)\n"
    "- zenn_title: Zenn向け日本語タイトル(40文字程度、技術者の好奇心を刺激する表現)\n"
    "- zenn_sections: H2見出し候補を3〜5個の文字列リストで出力\n"
    "- zenn_intro: 記事の冒頭に置く導入文(200字程度)\n"
    "- zenn_tags: Zennのタグ候補を正確に3個の文字列リストで出力\n\n"
    "# 8. 必須処理ルール\n"
    "- evaluation_reason を最初に記述することで思考の根拠を確立してから他フィールドを生成すること。\n"
    "- <previous_feedback> タグが与えられた場合、その指摘を必ず反映して再生成すること。\n"
)

EVALUATE_SYSTEM_PROMPT = (
    "あなたは生成されたコンテンツの品質をチェックする厳格なレビュアーです。\n"
    "与えられた記事分析結果を評価し、以下の基準で合否(passed)を判定してください。\n\n"
    "# 判定基準\n"
    "- improved_title が元タイトルの直訳になっていないか(バズるタイトルの法則が適用されているか)\n"
    "- summary が記事の本質を的確に説明しているか(具体性に欠ける一般論になっていないか)\n"
    "- x_post が絵文字1個+本文+{URL}の形式を守り、内容が具体的か\n"
    "- viral_score の値が内容の説得力と整合しているか\n\n"
    "feedback には、不合格の場合に何を直せば良いかを日本語1〜2文で具体的に記述してください。"
    "合格の場合は feedback を空文字列にしてください。"
)
```

- [ ] **Step 3: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`(`google.genai.*` は既に `mypy.ini` で `ignore_missing_imports = true` 設定済み)

- [ ] **Step 4: コミット**

```bash
git add core/analysis/client.py core/analysis/prompts.py
git commit -m "feat: Geminiクライアント初期化とシステムプロンプトを追加"
```

---

### Task 5: core/analysis/parsing.py(TDD)

**Files:**
- Create: `core/analysis/parsing.py`
- Test: `tests/core/test_parsing.py`

**Interfaces:**
- Consumes: `core.analysis.schemas.ScoredDraft`, `core.analysis.schemas.GeneratedAnalysisJSON`, `core.analysis.schemas.EvaluationJSON`, `models.RawArticle`, `models.AnalysisCore`, `models.XDraft`, `models.ZennDraft`
- Produces: `strip_markdown_fences(text: str) -> str`, `parse_generation_response(raw_text: str, article: RawArticle) -> ScoredDraft`, `parse_evaluation_response(raw_text: str) -> EvaluationJSON`

- [ ] **Step 1: 失敗するテストを書く**

`tests/core/test_parsing.py` を作成:

```python
import json
import pytest
from pydantic import ValidationError
from core.analysis.parsing import (
    strip_markdown_fences,
    parse_generation_response,
    parse_evaluation_response,
)
from models import RawArticle


def _make_article(**kwargs: str) -> RawArticle:
    defaults: dict[str, str] = {
        "source_name": "Test Source",
        "category": "Tech",
        "title": "Test Title",
        "url": "https://example.com/test",
        "summary": "Test summary text.",
    }
    return RawArticle(**(defaults | kwargs))


# --- strip_markdown_fences ---

def test_strip_plain_json_unchanged() -> None:
    raw = '{"key": "value"}'
    assert strip_markdown_fences(raw) == raw


def test_strip_json_fences() -> None:
    raw = '```json\n{"key": "value"}\n```'
    assert strip_markdown_fences(raw) == '{"key": "value"}'


def test_strip_generic_fences() -> None:
    raw = '```\n{"key": "value"}\n```'
    assert strip_markdown_fences(raw) == '{"key": "value"}'


# --- parse_generation_response ---

VALID_GENERATION_PAYLOAD = {
    "evaluation_reason": "Next.jsに直結する内容のため関連度が高い。",
    "interest_score": 5,
    "business_value_score": 4,
    "novelty_score": 3,
    "viral_score": 4,
    "improved_title": "まだ○○で消耗してる?Next.js新機能まとめ",
    "summary": "Next.jsの新機能によりビルド速度が大幅に改善された。",
    "business_idea": "日本市場向けに導入支援コンサルティングを展開する。",
    "x_post": "🚀 Next.jsの新機能が発表されました。パフォーマンスが大幅に改善され、開発者体験も向上しています。",
    "zenn_title": "Next.js新機能を徹底解説",
    "zenn_sections": ["背景", "技術詳細", "まとめ"],
    "zenn_intro": "Next.jsの新機能について解説します。",
    "zenn_tags": ["Next.js", "React", "TypeScript"],
}


def test_parse_generation_response_valid_maps_all_fields() -> None:
    article = _make_article()
    draft = parse_generation_response(json.dumps(VALID_GENERATION_PAYLOAD), article)

    assert draft.raw == article
    assert draft.analysis.title == article.title
    assert draft.analysis.summary == VALID_GENERATION_PAYLOAD["summary"]
    assert draft.analysis.business_idea == VALID_GENERATION_PAYLOAD["business_idea"]
    assert draft.analysis.viral_score == VALID_GENERATION_PAYLOAD["viral_score"]
    assert draft.analysis.improved_title == VALID_GENERATION_PAYLOAD["improved_title"]
    assert draft.x.post == VALID_GENERATION_PAYLOAD["x_post"]
    assert draft.zenn.title == VALID_GENERATION_PAYLOAD["zenn_title"]
    assert draft.zenn.sections == VALID_GENERATION_PAYLOAD["zenn_sections"]
    assert draft.zenn.intro == VALID_GENERATION_PAYLOAD["zenn_intro"]
    assert draft.zenn.tags == VALID_GENERATION_PAYLOAD["zenn_tags"]
    assert draft.interest_score == 5
    assert draft.business_value_score == 4
    assert draft.novelty_score == 3


def test_parse_generation_response_rank_defaults_to_zero() -> None:
    article = _make_article()
    draft = parse_generation_response(json.dumps(VALID_GENERATION_PAYLOAD), article)
    assert draft.analysis.rank == 0


def test_parse_generation_response_with_markdown_fences() -> None:
    article = _make_article()
    raw = f"```json\n{json.dumps(VALID_GENERATION_PAYLOAD)}\n```"
    draft = parse_generation_response(raw, article)
    assert draft.analysis.summary == VALID_GENERATION_PAYLOAD["summary"]


def test_parse_generation_response_missing_key_raises() -> None:
    incomplete = {"evaluation_reason": "reason only"}
    article = _make_article()
    with pytest.raises(ValidationError):
        parse_generation_response(json.dumps(incomplete), article)


# --- parse_evaluation_response ---

def test_parse_evaluation_response_passed_true() -> None:
    payload = json.dumps({"passed": True, "feedback": ""})
    result = parse_evaluation_response(payload)
    assert result.passed is True
    assert result.feedback == ""


def test_parse_evaluation_response_passed_false_with_feedback() -> None:
    payload = json.dumps({"passed": False, "feedback": "improved_titleが直訳的です。"})
    result = parse_evaluation_response(payload)
    assert result.passed is False
    assert result.feedback == "improved_titleが直訳的です。"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python3 -m pytest tests/core/test_parsing.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'core.analysis.parsing'`)

- [ ] **Step 3: core/analysis/parsing.py を実装**

```python
import re
from core.analysis.schemas import ScoredDraft, GeneratedAnalysisJSON, EvaluationJSON
from models import RawArticle, AnalysisCore, XDraft, ZennDraft


def strip_markdown_fences(text: str) -> str:
    """```json ... ``` などのMarkdownコードブロックを除去する"""
    stripped = text.strip()
    return re.sub(r"^```[a-zA-Z]*\n?(.*?)\n?```$", r"\1", stripped, flags=re.DOTALL)


def parse_generation_response(raw_text: str, article: RawArticle) -> ScoredDraft:
    """Geminiの生成ステップのレスポンステキストをScoredDraftにマッピングする"""
    clean = strip_markdown_fences(raw_text)
    data = GeneratedAnalysisJSON.model_validate_json(clean)

    analysis = AnalysisCore(
        title=article.title,
        summary=data.summary,
        business_idea=data.business_idea,
        viral_score=data.viral_score,
        improved_title=data.improved_title,
        rank=0,  # rank_node が全記事のfan-in後に確定する
    )
    x = XDraft(post=data.x_post)
    zenn = ZennDraft(
        title=data.zenn_title,
        sections=data.zenn_sections,
        intro=data.zenn_intro,
        tags=data.zenn_tags,
    )
    return ScoredDraft(
        raw=article,
        analysis=analysis,
        x=x,
        zenn=zenn,
        interest_score=data.interest_score,
        business_value_score=data.business_value_score,
        novelty_score=data.novelty_score,
    )


def parse_evaluation_response(raw_text: str) -> EvaluationJSON:
    """Geminiの評価ステップのレスポンステキストをEvaluationJSONにマッピングする"""
    clean = strip_markdown_fences(raw_text)
    return EvaluationJSON.model_validate_json(clean)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python3 -m pytest tests/core/test_parsing.py -v`
Expected: 全件 PASS

- [ ] **Step 5: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`

- [ ] **Step 6: コミット**

```bash
git add core/analysis/parsing.py tests/core/test_parsing.py
git commit -m "feat: Gemini生成/評価レスポンスのパースロジックを追加"
```

---

### Task 6: core/analysis/generate.py(TDD)

**Files:**
- Create: `core/analysis/generate.py`
- Test: `tests/core/test_generate.py`

**Interfaces:**
- Consumes: `core.analysis.client.MODEL`, `core.analysis.prompts.GENERATE_SYSTEM_PROMPT`, `core.analysis.schemas.ScoredDraft`, `core.analysis.schemas.GeneratedAnalysisJSON`, `core.analysis.parsing.parse_generation_response`
- Produces: `build_generate_user_content(article: RawArticle, user_status: str, feedback: str | None) -> str`, `generate_draft(article: RawArticle, client: genai.Client, user_status: str = "", feedback: str | None = None) -> ScoredDraft`

- [ ] **Step 1: 失敗するテストを書く**

`tests/core/test_generate.py` を作成:

```python
import json
from unittest.mock import MagicMock
from core.analysis.generate import build_generate_user_content, generate_draft
from core.analysis.client import MODEL
from models import RawArticle


def _make_article(**kwargs: str) -> RawArticle:
    defaults: dict[str, str] = {
        "source_name": "Test Source",
        "category": "Tech",
        "title": "Test Title",
        "url": "https://example.com/test",
        "summary": "Test summary text.",
    }
    return RawArticle(**(defaults | kwargs))


# --- build_generate_user_content ---

def test_build_generate_user_content_without_status_or_feedback() -> None:
    article = _make_article(title="My Article", url="https://example.com/a", summary="A summary.")
    result = build_generate_user_content(article, "", None)
    assert "<user_interests>" not in result
    assert "<previous_feedback>" not in result
    assert "Title: My Article" in result
    assert "URL: https://example.com/a" in result
    assert "Summary:\nA summary." in result


def test_build_generate_user_content_with_status() -> None:
    article = _make_article()
    result = build_generate_user_content(article, "Next.js, 音楽生成AI", None)
    assert "<user_interests>" in result
    assert "Next.js, 音楽生成AI" in result
    assert result.index("<user_interests>") < result.index("Title:")


def test_build_generate_user_content_with_feedback() -> None:
    article = _make_article()
    result = build_generate_user_content(article, "", "improved_titleが直訳的です。")
    assert "<previous_feedback>" in result
    assert "improved_titleが直訳的です。" in result
    assert result.index("<previous_feedback>") < result.index("Title:")


def test_build_generate_user_content_status_before_feedback() -> None:
    article = _make_article()
    result = build_generate_user_content(article, "Next.js", "フィードバック本文")
    assert result.index("<user_interests>") < result.index("<previous_feedback>")


# --- generate_draft ---

VALID_GENERATION_PAYLOAD = {
    "evaluation_reason": "reason",
    "interest_score": 5,
    "business_value_score": 4,
    "novelty_score": 3,
    "viral_score": 4,
    "improved_title": "改善タイトル",
    "summary": "要約",
    "business_idea": "アイデア",
    "x_post": "🚀 本文 {URL}",
    "zenn_title": "Zennタイトル",
    "zenn_sections": ["1", "2", "3"],
    "zenn_intro": "導入文",
    "zenn_tags": ["A", "B", "C"],
}


def test_generate_draft_calls_api_once_with_correct_model() -> None:
    article = _make_article()
    mock_response = MagicMock()
    mock_response.text = json.dumps(VALID_GENERATION_PAYLOAD)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    generate_draft(article, client=mock_client)

    mock_client.models.generate_content.assert_called_once()
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == MODEL


def test_generate_draft_returns_scored_draft_for_correct_article() -> None:
    article = _make_article(title="Specific Title")
    mock_response = MagicMock()
    mock_response.text = json.dumps(VALID_GENERATION_PAYLOAD)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    draft = generate_draft(article, client=mock_client)

    assert draft.raw.title == "Specific Title"
    assert draft.analysis.summary == "要約"


def test_generate_draft_includes_feedback_in_prompt() -> None:
    article = _make_article()
    mock_response = MagicMock()
    mock_response.text = json.dumps(VALID_GENERATION_PAYLOAD)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    generate_draft(article, client=mock_client, feedback="タイトルを見直してください。")

    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert "タイトルを見直してください。" in call_kwargs["contents"]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python3 -m pytest tests/core/test_generate.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'core.analysis.generate'`)

- [ ] **Step 3: core/analysis/generate.py を実装**

```python
from google import genai
from google.genai import types
from models import RawArticle
from core.analysis.client import MODEL
from core.analysis.prompts import GENERATE_SYSTEM_PROMPT
from core.analysis.schemas import ScoredDraft, GeneratedAnalysisJSON
from core.analysis.parsing import parse_generation_response


def build_generate_user_content(article: RawArticle, user_status: str, feedback: str | None) -> str:
    """Gemini生成ステップへ渡すuser_content文字列を組み立てる"""
    parts: list[str] = []
    if user_status:
        parts.append(f"<user_interests>\n{user_status}\n</user_interests>")
    if feedback:
        parts.append(f"<previous_feedback>\n{feedback}\n</previous_feedback>")
    parts.append(
        f"Title: {article.title}\n"
        f"URL: {article.url}\n"
        f"Source: {article.source_name} / {article.category}\n\n"
        f"Summary:\n{article.summary}"
    )
    return "\n\n".join(parts)


def generate_draft(
    article: RawArticle,
    client: genai.Client,
    user_status: str = "",
    feedback: str | None = None,
) -> ScoredDraft:
    """RawArticle 1件をGeminiに渡し、ScoredDraftを返す"""
    user_content = build_generate_user_content(article, user_status, feedback)

    response = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=GENERATE_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=GeneratedAnalysisJSON,
            temperature=0.2,
            max_output_tokens=4096,
        ),
    )

    raw_text = response.text
    if raw_text is None:
        raise ValueError("Gemini から空のレスポンスが返されました。")
    return parse_generation_response(raw_text, article)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python3 -m pytest tests/core/test_generate.py -v`
Expected: 全件 PASS

- [ ] **Step 5: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`

- [ ] **Step 6: コミット**

```bash
git add core/analysis/generate.py tests/core/test_generate.py
git commit -m "feat: 記事1件の分析生成ロジック(generate_draft)を追加"
```

---

### Task 7: core/analysis/evaluate.py(TDD)

**Files:**
- Create: `core/analysis/evaluate.py`
- Test: `tests/core/test_evaluate.py`

**Interfaces:**
- Consumes: `core.analysis.schemas.ScoredDraft`, `core.analysis.schemas.EvaluationJSON`, `core.analysis.prompts.EVALUATE_SYSTEM_PROMPT`, `core.analysis.client.MODEL`, `core.analysis.parsing.parse_evaluation_response`
- Produces: `run_programmatic_checks(draft: ScoredDraft) -> list[str]`, `build_evaluate_user_content(article: RawArticle, draft: ScoredDraft) -> str`, `evaluate_draft(article: RawArticle, draft: ScoredDraft, client: genai.Client) -> tuple[bool, str]`

- [ ] **Step 1: 失敗するテストを書く**

`tests/core/test_evaluate.py` を作成:

```python
import json
from unittest.mock import MagicMock
from core.analysis.evaluate import (
    run_programmatic_checks,
    build_evaluate_user_content,
    evaluate_draft,
)
from models import RawArticle, AnalysisCore, XDraft, ZennDraft
from core.analysis.schemas import ScoredDraft


def _make_article(**kwargs: str) -> RawArticle:
    defaults: dict[str, str] = {
        "source_name": "Test Source",
        "category": "Tech",
        "title": "Test Title",
        "url": "https://example.com/test",
        "summary": "Test summary text.",
    }
    return RawArticle(**(defaults | kwargs))


def _make_scored_draft(**overrides: object) -> ScoredDraft:
    valid_x_post = "🚀 " + ("あ" * 110) + " {URL}"  # {URL}除いて約112字(100〜130字の範囲内)
    defaults: dict[str, object] = {
        "raw": _make_article(),
        "analysis": AnalysisCore(
            title="Test Title",
            summary="要約",
            business_idea="アイデア",
            viral_score=3,
            improved_title="改善タイトル",
            rank=0,
        ),
        "x": XDraft(post=valid_x_post),
        "zenn": ZennDraft(title="Zennタイトル", sections=["1", "2", "3"], intro="導入文", tags=["A", "B", "C"]),
        "interest_score": 3,
        "business_value_score": 3,
        "novelty_score": 3,
    }
    return ScoredDraft(**(defaults | overrides))  # type: ignore[arg-type]


# --- run_programmatic_checks ---

def test_run_programmatic_checks_passes_valid_draft() -> None:
    draft = _make_scored_draft()
    assert run_programmatic_checks(draft) == []


def test_run_programmatic_checks_flags_short_x_post() -> None:
    draft = _make_scored_draft(x=XDraft(post="短い {URL}"))
    violations = run_programmatic_checks(draft)
    assert any("x_post" in v for v in violations)


def test_run_programmatic_checks_flags_long_x_post() -> None:
    too_long = "🚀 " + ("あ" * 200) + " {URL}"
    draft = _make_scored_draft(x=XDraft(post=too_long))
    violations = run_programmatic_checks(draft)
    assert any("x_post" in v for v in violations)


def test_run_programmatic_checks_flags_invalid_viral_score() -> None:
    draft = _make_scored_draft(
        analysis=AnalysisCore(
            title="Test Title", summary="要約", business_idea="アイデア",
            viral_score=6, improved_title="改善タイトル", rank=0,
        )
    )
    violations = run_programmatic_checks(draft)
    assert any("viral_score" in v for v in violations)


def test_run_programmatic_checks_flags_wrong_tag_count() -> None:
    draft = _make_scored_draft(zenn=ZennDraft(title="T", sections=["1"], intro="I", tags=["A", "B"]))
    violations = run_programmatic_checks(draft)
    assert any("zenn_tags" in v for v in violations)


# --- build_evaluate_user_content ---

def test_build_evaluate_user_content_contains_key_fields() -> None:
    article = _make_article(title="Original")
    draft = _make_scored_draft()
    result = build_evaluate_user_content(article, draft)
    assert "Original" in result
    assert "改善タイトル" in result
    assert "要約" in result


# --- evaluate_draft ---

def test_evaluate_draft_skips_llm_when_programmatic_fails() -> None:
    article = _make_article()
    draft = _make_scored_draft(x=XDraft(post="短い {URL}"))
    mock_client = MagicMock()

    passed, feedback = evaluate_draft(article, draft, client=mock_client)

    mock_client.models.generate_content.assert_not_called()
    assert passed is False
    assert "x_post" in feedback


def test_evaluate_draft_calls_llm_when_programmatic_passes() -> None:
    article = _make_article()
    draft = _make_scored_draft()
    mock_response = MagicMock()
    mock_response.text = json.dumps({"passed": True, "feedback": ""})
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    passed, feedback = evaluate_draft(article, draft, client=mock_client)

    mock_client.models.generate_content.assert_called_once()
    assert passed is True
    assert feedback == ""


def test_evaluate_draft_returns_feedback_on_llm_fail() -> None:
    article = _make_article()
    draft = _make_scored_draft()
    mock_response = MagicMock()
    mock_response.text = json.dumps({"passed": False, "feedback": "improved_titleが直訳的です。"})
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    passed, feedback = evaluate_draft(article, draft, client=mock_client)

    assert passed is False
    assert feedback == "improved_titleが直訳的です。"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python3 -m pytest tests/core/test_evaluate.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'core.analysis.evaluate'`)

- [ ] **Step 3: core/analysis/evaluate.py を実装**

```python
from google import genai
from google.genai import types
from models import RawArticle
from core.analysis.client import MODEL
from core.analysis.prompts import EVALUATE_SYSTEM_PROMPT
from core.analysis.schemas import ScoredDraft, EvaluationJSON
from core.analysis.parsing import parse_evaluation_response

X_POST_MIN_LENGTH = 100
X_POST_MAX_LENGTH = 130
VIRAL_SCORE_MIN = 1
VIRAL_SCORE_MAX = 5
ZENN_TAGS_COUNT = 3


def run_programmatic_checks(draft: ScoredDraft) -> list[str]:
    """機械的に判定できる品質チェック(LLM呼び出し不要)"""
    violations: list[str] = []

    x_post_length = len(draft.x.post.replace("{URL}", ""))
    if not (X_POST_MIN_LENGTH <= x_post_length <= X_POST_MAX_LENGTH):
        violations.append(
            f"x_post の文字数が範囲外です({x_post_length}字、期待値{X_POST_MIN_LENGTH}〜{X_POST_MAX_LENGTH}字)。"
        )

    if not (VIRAL_SCORE_MIN <= draft.analysis.viral_score <= VIRAL_SCORE_MAX):
        violations.append(
            f"viral_score が範囲外です({draft.analysis.viral_score})。"
            f"{VIRAL_SCORE_MIN}〜{VIRAL_SCORE_MAX}の整数にしてください。"
        )

    if len(draft.zenn.tags) != ZENN_TAGS_COUNT:
        violations.append(f"zenn_tags は{ZENN_TAGS_COUNT}個である必要があります(現在{len(draft.zenn.tags)}個)。")

    return violations


def build_evaluate_user_content(article: RawArticle, draft: ScoredDraft) -> str:
    return (
        f"Original Title: {article.title}\n\n"
        f"improved_title: {draft.analysis.improved_title}\n"
        f"summary: {draft.analysis.summary}\n"
        f"business_idea: {draft.analysis.business_idea}\n"
        f"viral_score: {draft.analysis.viral_score}\n"
        f"x_post: {draft.x.post}\n"
    )


def evaluate_draft(
    article: RawArticle,
    draft: ScoredDraft,
    client: genai.Client,
) -> tuple[bool, str]:
    """機械的チェック→LLM自己評価の順で品質ゲートを判定する"""
    violations = run_programmatic_checks(draft)
    if violations:
        return False, " / ".join(violations)

    user_content = build_evaluate_user_content(article, draft)
    response = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=EVALUATE_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=EvaluationJSON,
            temperature=0.0,
            max_output_tokens=512,
        ),
    )

    raw_text = response.text
    if raw_text is None:
        raise ValueError("Gemini から空のレスポンスが返されました。")
    result = parse_evaluation_response(raw_text)
    return result.passed, result.feedback
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python3 -m pytest tests/core/test_evaluate.py -v`
Expected: 全件 PASS

- [ ] **Step 5: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`

- [ ] **Step 6: コミット**

```bash
git add core/analysis/evaluate.py tests/core/test_evaluate.py
git commit -m "feat: 生成物の自己評価ロジック(quality gate)を追加"
```

---

### Task 8: core/ranking.py(TDD)

**Files:**
- Create: `core/ranking.py`
- Test: `tests/core/test_ranking.py`

**Interfaces:**
- Consumes: `core.analysis.schemas.ScoredDraft`, `models.ProcessedArticle`
- Produces: `rank_scored_drafts(scored: list[ScoredDraft]) -> list[ProcessedArticle]`

- [ ] **Step 1: 失敗するテストを書く**

`tests/core/test_ranking.py` を作成:

```python
from core.ranking import rank_scored_drafts
from models import RawArticle, AnalysisCore, XDraft, ZennDraft
from core.analysis.schemas import ScoredDraft


def _make_scored_draft(
    url: str = "https://example.com/test",
    interest_score: int = 3,
    business_value_score: int = 3,
    novelty_score: int = 3,
) -> ScoredDraft:
    raw = RawArticle(
        source_name="Test Source", category="Tech", title="Test Title", url=url, summary="summary",
    )
    return ScoredDraft(
        raw=raw,
        analysis=AnalysisCore(
            title="Test Title", summary="要約", business_idea="アイデア",
            viral_score=3, improved_title="改善タイトル", rank=0,
        ),
        x=XDraft(post="post {URL}"),
        zenn=ZennDraft(title="T", sections=["1"], intro="I", tags=["A", "B", "C"]),
        interest_score=interest_score,
        business_value_score=business_value_score,
        novelty_score=novelty_score,
    )


def test_rank_scored_drafts_empty_list_returns_empty() -> None:
    assert rank_scored_drafts([]) == []


def test_rank_scored_drafts_higher_weighted_score_ranks_first() -> None:
    # weighted = interest*0.5 + business*0.3 + novelty*0.2
    high = _make_scored_draft(url="https://example.com/high", interest_score=4, business_value_score=2, novelty_score=1)  # 2.8
    low = _make_scored_draft(url="https://example.com/low", interest_score=1, business_value_score=1, novelty_score=1)  # 1.0

    ranked = rank_scored_drafts([low, high])  # 入力順は逆

    assert ranked[0].raw.url == "https://example.com/high"
    assert ranked[1].raw.url == "https://example.com/low"


def test_rank_scored_drafts_assigns_sequential_rank_from_1() -> None:
    drafts = [
        _make_scored_draft(url="https://example.com/a", interest_score=5, business_value_score=5, novelty_score=5),
        _make_scored_draft(url="https://example.com/b", interest_score=1, business_value_score=1, novelty_score=1),
        _make_scored_draft(url="https://example.com/c", interest_score=3, business_value_score=3, novelty_score=3),
    ]

    ranked = rank_scored_drafts(drafts)

    assert [a.analysis.rank for a in ranked] == [1, 2, 3]


def test_rank_scored_drafts_preserves_analysis_content() -> None:
    draft = _make_scored_draft()
    ranked = rank_scored_drafts([draft])
    assert ranked[0].analysis.summary == "要約"
    assert ranked[0].analysis.improved_title == "改善タイトル"
    assert ranked[0].x.post == "post {URL}"
    assert ranked[0].zenn.title == "T"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python3 -m pytest tests/core/test_ranking.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'core.ranking'`)

- [ ] **Step 3: core/ranking.py を実装**

```python
from core.analysis.schemas import ScoredDraft
from models import ProcessedArticle

INTEREST_WEIGHT = 0.5
BUSINESS_VALUE_WEIGHT = 0.3
NOVELTY_WEIGHT = 0.2


def _weighted_score(draft: ScoredDraft) -> float:
    return (
        draft.interest_score * INTEREST_WEIGHT
        + draft.business_value_score * BUSINESS_VALUE_WEIGHT
        + draft.novelty_score * NOVELTY_WEIGHT
    )


def rank_scored_drafts(scored: list[ScoredDraft]) -> list[ProcessedArticle]:
    """軸別スコアの重み付け合計で降順ソートし、rankを確定したProcessedArticleのリストを返す"""
    ordered = sorted(scored, key=_weighted_score, reverse=True)
    ranked: list[ProcessedArticle] = []
    for i, draft in enumerate(ordered, start=1):
        analysis = draft.analysis.model_copy(update={"rank": i})
        ranked.append(ProcessedArticle(raw=draft.raw, analysis=analysis, x=draft.x, zenn=draft.zenn))
    return ranked
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python3 -m pytest tests/core/test_ranking.py -v`
Expected: 全件 PASS

- [ ] **Step 5: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`

- [ ] **Step 6: コミット**

```bash
git add core/ranking.py tests/core/test_ranking.py
git commit -m "feat: fan-in後の重み付けランキングロジックを追加"
```

---

### Task 9: core/reporting.py

**Files:**
- Create: `core/reporting.py`

**Interfaces:**
- Consumes: `models.ProcessedArticle`
- Produces: `format_console_report(ranked: list[ProcessedArticle], user_status: str) -> str`, `save_markdown_report(ranked: list[ProcessedArticle], user_status: str) -> str`(戻り値は保存先パス文字列)

このファイルは単純な文字列整形・ファイル書き込みのみで複雑な分岐ロジックを含まないため、CLAUDE.md 憲法②の対象外(`fetcher.py`と同様の扱い)。pytestは書かず、Step 3の手動実行で疎通確認する。

- [ ] **Step 1: core/reporting.py を作成**

```python
import pathlib
from datetime import date
from models import ProcessedArticle

OUTPUTS_DIR = pathlib.Path("outputs")


def format_console_report(ranked: list[ProcessedArticle], user_status: str) -> str:
    lines: list[str] = ["=" * 60, "  leanshift-trend-bot | LangGraph版", "=" * 60]
    if user_status:
        lines.append(f"\n[ユーザーステータス] {user_status}")

    for article in ranked:
        stars = "⭐" * article.analysis.viral_score if article.analysis.viral_score > 0 else "—"
        lines += [
            f"\n【第 {article.analysis.rank} 位】{stars} [{article.raw.source_name}] {article.analysis.improved_title}",
            f"  元記事: {article.raw.title}",
            f"  URL: {article.raw.url}",
            "",
            f"  ▶ 要約\n    {article.analysis.summary}",
            "",
            f"  ▶ マネタイズアイデア\n    {article.analysis.business_idea}",
            "",
            f"  ▶ X投稿下書き\n    {article.x.post.replace('{URL}', article.raw.url)}",
            "-" * 60,
        ]
    return "\n".join(lines)


def save_markdown_report(ranked: list[ProcessedArticle], user_status: str) -> str:
    """分析結果を outputs/YYYY-MM-DD_trends.md として保存し、パスを返す"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    output_path = OUTPUTS_DIR / f"{today}_trends.md"

    lines: list[str] = [f"# Trend Report — {today}", ""]
    if user_status:
        lines += ["## ユーザーステータス", "", user_status, "", "---", ""]

    for article in ranked:
        stars = "⭐" * article.analysis.viral_score if article.analysis.viral_score > 0 else "—"
        section_list = "\n".join(f"- {s}" for s in article.zenn.sections)
        tag_list = " / ".join(f"`{t}`" for t in article.zenn.tags)
        lines += [
            f"## 第 {article.analysis.rank} 位 — [{article.raw.source_name}] {article.analysis.improved_title}",
            "",
            f"- **元記事:** {article.raw.title}",
            f"- **URL:** {article.raw.url}",
            f"- **🔥 バズ度:** {stars} ({article.analysis.viral_score}/5)",
            "",
            "### 要約",
            "",
            article.analysis.summary,
            "",
            "### 📝 Zenn構成案",
            "",
            f"**タイトル:** {article.zenn.title}",
            "",
            "**見出し構成:**",
            "",
            section_list,
            "",
            "**導入文:**",
            "",
            article.zenn.intro,
            "",
            f"**タグ:** {tag_list}",
            "",
            "### マネタイズアイデア",
            "",
            article.analysis.business_idea,
            "",
            "### 📣 X投稿下書き",
            "",
            "```",
            article.x.post.replace("{URL}", article.raw.url),
            "```",
            "",
            "---",
            "",
        ]

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)
```

- [ ] **Step 2: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`

- [ ] **Step 3: 手動疎通確認**

Run:
```bash
python3 -c "
from models import RawArticle, AnalysisCore, XDraft, ZennDraft, ProcessedArticle
from core.reporting import format_console_report, save_markdown_report

article = ProcessedArticle(
    raw=RawArticle(source_name='Test', category='Tech', title='T', url='https://example.com', summary='s'),
    analysis=AnalysisCore(title='T', summary='要約', business_idea='アイデア', viral_score=3, improved_title='改善T', rank=1),
    x=XDraft(post='post {URL}'),
    zenn=ZennDraft(title='Zタイトル', sections=['a'], intro='導入', tags=['x','y','z']),
)
print(format_console_report([article], 'テスト関心事'))
path = save_markdown_report([article], 'テスト関心事')
print('saved to', path)
"
```
Expected: コンソールに整形されたレポートが表示され、`outputs/YYYY-MM-DD_trends.md` が作成される(このテスト実行で作成された `outputs/` 配下のファイルはテスト用途のため削除して構わない)

- [ ] **Step 4: コミット**

```bash
git add core/reporting.py
git commit -m "feat: Markdownレポート生成とコンソール整形ロジックを追加"
```

---

### Task 10: orchestration/langgraph_app/state.py(TDD reducer)

**Files:**
- Create: `orchestration/langgraph_app/state.py`
- Test: `tests/orchestration/test_state.py`

**Interfaces:**
- Consumes: `models.RawArticle`, `models.ProcessedArticle`, `core.analysis.schemas.ScoredDraft`
- Produces: `merge_by_url(existing: list[RawArticle], new: list[RawArticle]) -> list[RawArticle]`, `merge_by_article_id(existing: list[ScoredDraft], new: list[ScoredDraft]) -> list[ScoredDraft]`, `GraphState`(TypedDict、フィールド: `user_status: str`, `articles: Annotated[list[RawArticle], merge_by_url]`, `scored: Annotated[list[ScoredDraft], merge_by_article_id]`, `ranked: list[ProcessedArticle]`, `report_path: str`)、`ArticleState`(TypedDict、フィールド: `article: RawArticle`, `user_status: str`, `draft: ScoredDraft | None`, `feedback: str | None`, `iteration: int`)

- [ ] **Step 1: 失敗するテストを書く**

`tests/orchestration/test_state.py` を作成:

```python
from orchestration.langgraph_app.state import merge_by_url, merge_by_article_id
from models import RawArticle, AnalysisCore, XDraft, ZennDraft
from core.analysis.schemas import ScoredDraft


def _make_article(url: str) -> RawArticle:
    return RawArticle(source_name="S", category="Tech", title="T", url=url, summary="s")


def _make_scored(url: str) -> ScoredDraft:
    return ScoredDraft(
        raw=_make_article(url),
        analysis=AnalysisCore(title="T", summary="要約", business_idea="アイデア", viral_score=3, improved_title="改善", rank=0),
        x=XDraft(post="post"),
        zenn=ZennDraft(title="Z", sections=["1"], intro="I", tags=["a", "b", "c"]),
        interest_score=3, business_value_score=3, novelty_score=3,
    )


def test_merge_by_url_deduplicates_same_url() -> None:
    a = _make_article("https://example.com/a")
    a_dup = _make_article("https://example.com/a")
    result = merge_by_url([a], [a_dup])
    assert len(result) == 1


def test_merge_by_url_keeps_distinct_urls() -> None:
    a = _make_article("https://example.com/a")
    b = _make_article("https://example.com/b")
    result = merge_by_url([a], [b])
    assert len(result) == 2
    assert {r.url for r in result} == {"https://example.com/a", "https://example.com/b"}


def test_merge_by_url_new_overwrites_existing_for_same_url() -> None:
    a = _make_article("https://example.com/a")
    a_new = RawArticle(source_name="Updated", category="Tech", title="Updated", url="https://example.com/a", summary="s")
    result = merge_by_url([a], [a_new])
    assert len(result) == 1
    assert result[0].source_name == "Updated"


def test_merge_by_article_id_deduplicates_same_article() -> None:
    scored = _make_scored("https://example.com/a")
    # 同じ RawArticle(同一article_id)を含む更新は重複除外される
    result = merge_by_article_id([scored], [scored])
    assert len(result) == 1


def test_merge_by_article_id_keeps_distinct_articles() -> None:
    a = _make_scored("https://example.com/a")
    b = _make_scored("https://example.com/b")
    result = merge_by_article_id([a], [b])
    assert len(result) == 2
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python3 -m pytest tests/orchestration/test_state.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'orchestration.langgraph_app.state'`)

- [ ] **Step 3: orchestration/langgraph_app/state.py を実装**

```python
from typing import Annotated, TypedDict
from models import RawArticle, ProcessedArticle
from core.analysis.schemas import ScoredDraft


def merge_by_url(existing: list[RawArticle], new: list[RawArticle]) -> list[RawArticle]:
    """URLをキーに重複を排除しながらマージする(再実行・リトライ時の重複追加を防止)"""
    by_url = {a.url: a for a in existing}
    for a in new:
        by_url[a.url] = a
    return list(by_url.values())


def merge_by_article_id(existing: list[ScoredDraft], new: list[ScoredDraft]) -> list[ScoredDraft]:
    """article_idをキーに重複を排除しながらマージする(再実行・リトライ時の重複追加を防止)"""
    by_id = {d.raw.article_id: d for d in existing}
    for d in new:
        by_id[d.raw.article_id] = d
    return list(by_id.values())


class GraphState(TypedDict):
    user_status: str
    articles: Annotated[list[RawArticle], merge_by_url]
    scored: Annotated[list[ScoredDraft], merge_by_article_id]
    ranked: list[ProcessedArticle]
    report_path: str


class ArticleState(TypedDict):
    article: RawArticle
    user_status: str
    draft: ScoredDraft | None
    feedback: str | None
    iteration: int
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python3 -m pytest tests/orchestration/test_state.py -v`
Expected: 全件 PASS

- [ ] **Step 5: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`

- [ ] **Step 6: コミット**

```bash
git add orchestration/langgraph_app/state.py tests/orchestration/test_state.py
git commit -m "feat: GraphState/ArticleStateと重複防止カスタムreducerを追加"
```

---

### Task 11: orchestration/langgraph_app/subgraphs/article_analysis.py(TDD routing)

**Files:**
- Create: `orchestration/langgraph_app/subgraphs/article_analysis.py`
- Test: `tests/orchestration/test_article_analysis.py`

**Interfaces:**
- Consumes: `orchestration.langgraph_app.state.ArticleState`, `core.analysis.generate.generate_draft`, `core.analysis.evaluate.evaluate_draft`, `core.analysis.client.build_client`
- Produces: `MAX_ITERATIONS: int`(値は3)、`generate_node(state: ArticleState) -> dict`, `evaluate_node(state: ArticleState) -> dict`, `route_after_evaluate(state: ArticleState) -> str`, `build_article_analysis_subgraph() -> CompiledStateGraph`, `analyze_article_node(state: ArticleState) -> dict`(戻り値のキーは親グラフの`scored`)

- [ ] **Step 1: 失敗するテストを書く(route_after_evaluate と analyze_article_node)**

`tests/orchestration/test_article_analysis.py` を作成:

```python
import pytest
from unittest.mock import MagicMock
import orchestration.langgraph_app.subgraphs.article_analysis as article_analysis_module
from orchestration.langgraph_app.subgraphs.article_analysis import (
    route_after_evaluate,
    analyze_article_node,
    MAX_ITERATIONS,
)
from langgraph.graph import END
from models import RawArticle, AnalysisCore, XDraft, ZennDraft
from core.analysis.schemas import ScoredDraft
from orchestration.langgraph_app.state import ArticleState


def _make_article() -> RawArticle:
    return RawArticle(source_name="S", category="Tech", title="T", url="https://example.com/a", summary="s")


def _make_scored() -> ScoredDraft:
    return ScoredDraft(
        raw=_make_article(),
        analysis=AnalysisCore(title="T", summary="要約", business_idea="アイデア", viral_score=3, improved_title="改善", rank=0),
        x=XDraft(post="post"),
        zenn=ZennDraft(title="Z", sections=["1"], intro="I", tags=["a", "b", "c"]),
        interest_score=3, business_value_score=3, novelty_score=3,
    )


# --- route_after_evaluate ---

def test_route_after_evaluate_ends_when_feedback_none() -> None:
    state: ArticleState = {"article": _make_article(), "user_status": "", "draft": None, "feedback": None, "iteration": 1}
    assert route_after_evaluate(state) == END


def test_route_after_evaluate_continues_when_feedback_present_and_under_max() -> None:
    state: ArticleState = {"article": _make_article(), "user_status": "", "draft": None, "feedback": "直してください", "iteration": 1}
    assert route_after_evaluate(state) == "generate"


def test_route_after_evaluate_ends_when_max_iterations_reached_even_with_feedback() -> None:
    state: ArticleState = {"article": _make_article(), "user_status": "", "draft": None, "feedback": "直してください", "iteration": MAX_ITERATIONS}
    assert route_after_evaluate(state) == END


# --- analyze_article_node ---

def test_analyze_article_node_returns_scored_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    scored = _make_scored()
    fake_subgraph = MagicMock()
    fake_subgraph.invoke.return_value = {"draft": scored}
    monkeypatch.setattr(article_analysis_module, "_SUBGRAPH", fake_subgraph)

    state: ArticleState = {"article": _make_article(), "user_status": "", "draft": None, "feedback": None, "iteration": 0}
    result = analyze_article_node(state)

    assert result == {"scored": [scored]}


def test_analyze_article_node_returns_empty_scored_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_subgraph = MagicMock()
    fake_subgraph.invoke.side_effect = RuntimeError("API failure")
    monkeypatch.setattr(article_analysis_module, "_SUBGRAPH", fake_subgraph)

    state: ArticleState = {"article": _make_article(), "user_status": "", "draft": None, "feedback": None, "iteration": 0}
    result = analyze_article_node(state)

    assert result == {"scored": []}
```

`monkeypatch` はpytest組み込みfixtureのため、テスト関数の引数として自動的に注入される(import不要)。

- [ ] **Step 2: テストが失敗することを確認**

Run: `python3 -m pytest tests/orchestration/test_article_analysis.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'orchestration.langgraph_app.subgraphs.article_analysis'`)

- [ ] **Step 3: orchestration/langgraph_app/subgraphs/article_analysis.py を実装**

```python
import logging
from langgraph.graph import StateGraph, START, END
from orchestration.langgraph_app.state import ArticleState
from core.analysis.generate import generate_draft
from core.analysis.evaluate import evaluate_draft
from core.analysis.client import build_client

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3


def generate_node(state: ArticleState) -> dict:
    client = build_client()
    draft = generate_draft(
        state["article"],
        client=client,
        user_status=state["user_status"],
        feedback=state["feedback"],
    )
    return {"draft": draft}


def evaluate_node(state: ArticleState) -> dict:
    client = build_client()
    draft = state["draft"]
    assert draft is not None
    passed, feedback = evaluate_draft(state["article"], draft, client=client)
    return {
        "feedback": None if passed else feedback,
        "iteration": state["iteration"] + 1,
    }


def route_after_evaluate(state: ArticleState) -> str:
    if state["feedback"] is None or state["iteration"] >= MAX_ITERATIONS:
        return END
    return "generate"


def build_article_analysis_subgraph():
    builder = StateGraph(ArticleState)
    builder.add_node("generate", generate_node)
    builder.add_node("evaluate", evaluate_node)
    builder.add_edge(START, "generate")
    builder.add_edge("generate", "evaluate")
    builder.add_conditional_edges("evaluate", route_after_evaluate)
    return builder.compile()


_SUBGRAPH = build_article_analysis_subgraph()


def analyze_article_node(state: ArticleState) -> dict:
    """記事1件のサブグラフを実行し、親グラフのscoredキーへ結果を返す。
    最終的に失敗した記事はスキップし、パイプライン全体を止めない。"""
    try:
        result = _SUBGRAPH.invoke(state)
    except Exception:
        logger.exception("記事の分析に失敗しました: %s", state["article"].url)
        return {"scored": []}
    return {"scored": [result["draft"]]}
```

`build_article_analysis_subgraph` は戻り値型注釈を付けていない。`mypy.ini` は `strict = false`(`disallow_untyped_defs` 無効)のため、これはエラーにならない。LangGraphの`CompiledStateGraph`型は複雑なジェネリクスを要求するため、型注釈を明示するとかえって冗長になることを避けている。

- [ ] **Step 4: テストが通ることを確認**

Run: `python3 -m pytest tests/orchestration/test_article_analysis.py -v`
Expected: 全件 PASS

- [ ] **Step 5: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`(エラーが出る場合はエラーメッセージに従い該当箇所に `# type: ignore[エラーコード]` を追加すること)

- [ ] **Step 6: コミット**

```bash
git add orchestration/langgraph_app/subgraphs/article_analysis.py tests/orchestration/test_article_analysis.py
git commit -m "feat: generate→evaluate→improveループ(article_analysisサブグラフ)を追加"
```

---

### Task 12: orchestration/langgraph_app/nodes/fetch_nodes.py と dispatch.py(TDD dispatch)

**Files:**
- Create: `orchestration/langgraph_app/nodes/fetch_nodes.py`
- Create: `orchestration/langgraph_app/nodes/dispatch.py`
- Test: `tests/orchestration/test_dispatch.py`

**Interfaces:**
- Consumes: `core.sources.hackernews.fetch_hn_articles`, `core.sources.producthunt.fetch_product_hunt_articles`, `core.sources.techcrunch.fetch_techcrunch_articles`, `core.sources.reddit.fetch_reddit_articles`, `orchestration.langgraph_app.state.GraphState`, `orchestration.langgraph_app.state.ArticleState`
- Produces: `fetch_hn_node`, `fetch_ph_node`, `fetch_tc_node`, `fetch_reddit_node`(いずれも `(state: GraphState) -> dict`)、`dispatch_node(state: GraphState) -> dict`、`dispatch_to_analysis(state: GraphState) -> list[Send]`

- [ ] **Step 1: fetch_nodes.py を作成(テスト不要、外部I/Oのラッパーのため)**

```python
from core.sources.hackernews import fetch_hn_articles
from core.sources.producthunt import fetch_product_hunt_articles
from core.sources.techcrunch import fetch_techcrunch_articles
from core.sources.reddit import fetch_reddit_articles
from orchestration.langgraph_app.state import GraphState

FETCH_LIMIT = 3


def fetch_hn_node(state: GraphState) -> dict:
    return {"articles": fetch_hn_articles(limit=FETCH_LIMIT)}


def fetch_ph_node(state: GraphState) -> dict:
    return {"articles": fetch_product_hunt_articles(limit=FETCH_LIMIT)}


def fetch_tc_node(state: GraphState) -> dict:
    return {"articles": fetch_techcrunch_articles(limit=FETCH_LIMIT)}


def fetch_reddit_node(state: GraphState) -> dict:
    return {"articles": fetch_reddit_articles(limit=FETCH_LIMIT)}
```

- [ ] **Step 2: 失敗するテストを書く(dispatch_to_analysis)**

`tests/orchestration/test_dispatch.py` を作成:

```python
from langgraph.types import Send
from orchestration.langgraph_app.nodes.dispatch import dispatch_node, dispatch_to_analysis
from orchestration.langgraph_app.state import GraphState
from models import RawArticle


def _make_article(url: str) -> RawArticle:
    return RawArticle(source_name="S", category="Tech", title="T", url=url, summary="s")


def test_dispatch_node_returns_empty_dict() -> None:
    state: GraphState = {"user_status": "", "articles": [], "scored": [], "ranked": [], "report_path": ""}
    assert dispatch_node(state) == {}


def test_dispatch_to_analysis_creates_one_send_per_article() -> None:
    articles = [_make_article("https://a.com"), _make_article("https://b.com")]
    state: GraphState = {"user_status": "Next.js", "articles": articles, "scored": [], "ranked": [], "report_path": ""}

    sends = dispatch_to_analysis(state)

    assert len(sends) == 2
    assert all(isinstance(s, Send) for s in sends)


def test_dispatch_to_analysis_send_targets_analyze_article_node() -> None:
    articles = [_make_article("https://a.com")]
    state: GraphState = {"user_status": "", "articles": articles, "scored": [], "ranked": [], "report_path": ""}

    sends = dispatch_to_analysis(state)

    assert sends[0].node == "analyze_article"


def test_dispatch_to_analysis_payload_initializes_correctly() -> None:
    articles = [_make_article("https://a.com")]
    state: GraphState = {"user_status": "Next.js", "articles": articles, "scored": [], "ranked": [], "report_path": ""}

    sends = dispatch_to_analysis(state)
    payload = sends[0].arg

    assert payload["article"] == articles[0]
    assert payload["user_status"] == "Next.js"
    assert payload["draft"] is None
    assert payload["feedback"] is None
    assert payload["iteration"] == 0
```

- [ ] **Step 3: テストが失敗することを確認**

Run: `python3 -m pytest tests/orchestration/test_dispatch.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'orchestration.langgraph_app.nodes.dispatch'`)

- [ ] **Step 4: dispatch.py を実装**

```python
from langgraph.types import Send
from orchestration.langgraph_app.state import GraphState, ArticleState


def dispatch_node(state: GraphState) -> dict:
    """Send APIによるfan-outの起点となるno-opノード(条件付きエッジはノードからしか発行できないため必要)"""
    return {}


def dispatch_to_analysis(state: GraphState) -> list[Send]:
    return [
        Send(
            "analyze_article",
            ArticleState(
                article=article,
                user_status=state["user_status"],
                draft=None,
                feedback=None,
                iteration=0,
            ),
        )
        for article in state["articles"]
    ]
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python3 -m pytest tests/orchestration/test_dispatch.py -v`
Expected: 全件 PASS

- [ ] **Step 6: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`

- [ ] **Step 7: コミット**

```bash
git add orchestration/langgraph_app/nodes/fetch_nodes.py orchestration/langgraph_app/nodes/dispatch.py tests/orchestration/test_dispatch.py
git commit -m "feat: 4ソース並列fetchノードとSend APIによるfan-outディスパッチを追加"
```

---

### Task 13: orchestration/langgraph_app/nodes/rank_node.py と report_node.py

**Files:**
- Create: `orchestration/langgraph_app/nodes/rank_node.py`
- Create: `orchestration/langgraph_app/nodes/report_node.py`

**Interfaces:**
- Consumes: `core.ranking.rank_scored_drafts`, `core.reporting.save_markdown_report`, `orchestration.langgraph_app.state.GraphState`
- Produces: `rank_node(state: GraphState) -> dict`, `report_node(state: GraphState) -> dict`

このタスクは既にテスト済みのcore関数を呼ぶだけの薄いラッパーのため、追加のpytestは書かない。

- [ ] **Step 1: rank_node.py を作成**

```python
from core.ranking import rank_scored_drafts
from orchestration.langgraph_app.state import GraphState


def rank_node(state: GraphState) -> dict:
    ranked = rank_scored_drafts(state["scored"])
    return {"ranked": ranked}
```

- [ ] **Step 2: report_node.py を作成**

```python
from core.reporting import save_markdown_report
from orchestration.langgraph_app.state import GraphState


def report_node(state: GraphState) -> dict:
    """レポートのファイル保存のみを行う(コンソール出力はmain.pyの責務)"""
    path = save_markdown_report(state["ranked"], state["user_status"])
    return {"report_path": path}
```

- [ ] **Step 3: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`

- [ ] **Step 4: コミット**

```bash
git add orchestration/langgraph_app/nodes/rank_node.py orchestration/langgraph_app/nodes/report_node.py
git commit -m "feat: ランキングノードとレポート保存ノードを追加"
```

---

### Task 14: orchestration/langgraph_app/checkpointer.py

**Files:**
- Create: `orchestration/langgraph_app/checkpointer.py`

**Interfaces:**
- Produces: `build_checkpointer() -> AsyncContextManager[AsyncSqliteSaver]`(非同期コンテキストマネージャ、WALモード有効化・`setup()`済みの`AsyncSqliteSaver`をyieldする)

- [ ] **Step 1: checkpointer.py を作成**

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

CHECKPOINT_DB_PATH = "checkpoints.sqlite"


@asynccontextmanager
async def build_checkpointer() -> AsyncIterator[AsyncSqliteSaver]:
    async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as checkpointer:
        await checkpointer.conn.execute("PRAGMA journal_mode=WAL")
        await checkpointer.setup()
        yield checkpointer
```

- [ ] **Step 2: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`(型スタブ不足のエラーが出た場合は `mypy.ini` に以下を追記する)

```ini
[mypy-langgraph.checkpoint.sqlite.*]
ignore_missing_imports = true
```

- [ ] **Step 3: 手動疎通確認**

Run:
```bash
python3 -c "
import asyncio
from orchestration.langgraph_app.checkpointer import build_checkpointer

async def main():
    async with build_checkpointer() as cp:
        print('checkpointer ready:', type(cp).__name__)

asyncio.run(main())
"
```
Expected: `checkpointer ready: AsyncSqliteSaver` が出力され、リポジトリ直下に `checkpoints.sqlite` が作成される(このファイルは `.gitignore` 済みでコミット対象外)

- [ ] **Step 4: コミット**

```bash
git add orchestration/langgraph_app/checkpointer.py
git add mypy.ini  # Step 2で追記した場合のみ
git commit -m "feat: AsyncSqliteSaverチェックポイント(WALモード)を追加"
```

---

### Task 15: orchestration/langgraph_app/graph.py と langgraph.json

**Files:**
- Create: `orchestration/langgraph_app/graph.py`
- Create: `langgraph.json`

**Interfaces:**
- Consumes: 全ノード・サブグラフ(Task 10〜13で作成したもの一式)
- Produces: `build_graph(checkpointer=None)`(型注釈なし、詳細はStep 1のコード参照)、モジュールレベル変数 `graph`(Studio用、checkpointer未指定でcompile)

- [ ] **Step 1: graph.py を作成**

```python
from langgraph.graph import StateGraph, START, END
from orchestration.langgraph_app.state import GraphState
from orchestration.langgraph_app.nodes.fetch_nodes import (
    fetch_hn_node,
    fetch_ph_node,
    fetch_tc_node,
    fetch_reddit_node,
)
from orchestration.langgraph_app.nodes.dispatch import dispatch_node, dispatch_to_analysis
from orchestration.langgraph_app.subgraphs.article_analysis import analyze_article_node
from orchestration.langgraph_app.nodes.rank_node import rank_node
from orchestration.langgraph_app.nodes.report_node import report_node


def build_graph(checkpointer=None):
    builder = StateGraph(GraphState)

    builder.add_node("fetch_hn", fetch_hn_node)
    builder.add_node("fetch_ph", fetch_ph_node)
    builder.add_node("fetch_tc", fetch_tc_node)
    builder.add_node("fetch_reddit", fetch_reddit_node)
    builder.add_node("dispatch", dispatch_node)
    builder.add_node("analyze_article", analyze_article_node)
    builder.add_node("rank", rank_node)
    builder.add_node("report", report_node)

    builder.add_edge(START, "fetch_hn")
    builder.add_edge(START, "fetch_ph")
    builder.add_edge(START, "fetch_tc")
    builder.add_edge(START, "fetch_reddit")
    builder.add_edge("fetch_hn", "dispatch")
    builder.add_edge("fetch_ph", "dispatch")
    builder.add_edge("fetch_tc", "dispatch")
    builder.add_edge("fetch_reddit", "dispatch")
    builder.add_conditional_edges("dispatch", dispatch_to_analysis)
    builder.add_edge("analyze_article", "rank")
    builder.add_edge("rank", "report")
    builder.add_edge("report", END)

    return builder.compile(checkpointer=checkpointer)


graph = build_graph()  # LangGraph Studio用(checkpointer未指定、langgraph devのローカル開発用チェックポインタに委ねる)
```

- [ ] **Step 2: langgraph.json を作成**

```json
{
  "dependencies": ["."],
  "graphs": {
    "leanshift_trend_bot": "orchestration/langgraph_app/graph.py:graph"
  },
  "env": ".env"
}
```

- [ ] **Step 3: インポート・グラフ構築の疎通確認**

Run: `python3 -c "from orchestration.langgraph_app.graph import build_graph, graph; print('nodes:', sorted(graph.get_graph().nodes.keys()))"`
Expected: `nodes: [...]` に `__start__`, `analyze_article`, `dispatch`, `fetch_hn`, `fetch_ph`, `fetch_reddit`, `fetch_tc`, `rank`, `report` が含まれることを確認する

- [ ] **Step 4: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`

- [ ] **Step 5: コミット**

```bash
git add orchestration/langgraph_app/graph.py langgraph.json
git commit -m "feat: LangGraphのグラフ組み立てとlanggraph.json(Studio対応)を追加"
```

---

### Task 16: main.py の書き換え

**Files:**
- Modify: `main.py`(全面書き換え)

**Interfaces:**
- Consumes: `orchestration.langgraph_app.graph.build_graph`, `orchestration.langgraph_app.checkpointer.build_checkpointer`, `orchestration.langgraph_app.state.GraphState`, `core.reporting.format_console_report`

- [ ] **Step 1: main.py を全面書き換え**

```python
import asyncio
import pathlib
from datetime import date
from orchestration.langgraph_app.graph import build_graph
from orchestration.langgraph_app.checkpointer import build_checkpointer
from orchestration.langgraph_app.state import GraphState
from core.reporting import format_console_report

USER_STATUS_PATH = pathlib.Path("my_status.txt")
MAX_CONCURRENCY = 5


def load_user_status() -> str:
    try:
        return USER_STATUS_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


async def run() -> None:
    user_status = load_user_status()

    print("=" * 60)
    print("  leanshift-trend-bot | LangGraph版")
    print("=" * 60)
    if user_status:
        print(f"\n[ユーザーステータス] {user_status}")

    initial_state: GraphState = {
        "user_status": user_status,
        "articles": [],
        "scored": [],
        "ranked": [],
        "report_path": "",
    }
    thread_id = f"run-{date.today().isoformat()}"

    async with build_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        final_state = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}, "max_concurrency": MAX_CONCURRENCY},
        )

    print(format_console_report(final_state["ranked"], user_status))
    print(f"\n{len(final_state['ranked'])}/{len(final_state['articles'])} 件処理成功")
    print(f"\n[保存完了] {final_state['report_path']}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: mypy 実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`

- [ ] **Step 3: コミット**

```bash
git add main.py
git commit -m "refactor: main.pyをLangGraphの非同期グラフ実行に書き換え"
```

---

### Task 17: 旧ファイルの削除とドキュメント整合

**Files:**
- Delete: `analyzer.py`
- Delete: `tests/test_analyzer.py`(新テストで機能的に置き換え済み)
- Modify: `docs/ARCHITECTURE.md`(冒頭に移行後アーキテクチャへのポインタを追記)

- [ ] **Step 1: 旧 analyzer.py と旧テストを削除**

Run:
```bash
git rm analyzer.py
git rm tests/test_analyzer.py
```

- [ ] **Step 2: docs/ARCHITECTURE.md の冒頭に移行済みである旨のポインタを追記**

`docs/ARCHITECTURE.md` の1行目(`# プロジェクト・アーキテクチャ概要書 (ARCHITECTURE)`)の直後に以下を挿入する:

```markdown
> **注意:** 本書は移行前(線形パイプライン)時点の記述です。LangGraph移行後の設計は
> `docs/superpowers/specs/2026-08-14-langgraph-migration-design.md` を参照してください。
> `fetcher.py` / `analyzer.py` は `core/` と `orchestration/langgraph_app/` に分割・移設されています。
```

- [ ] **Step 3: リポジトリ全体で mypy を実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`(削除したファイルへの参照が残っていないことを確認)

- [ ] **Step 4: リポジトリ全体で pytest を実行**

Run: `python3 -m pytest -v`
Expected: 全件 PASS(旧`tests/test_analyzer.py`の24件が姿を消し、Task 5〜12で追加したテストのみが残ることを確認)

- [ ] **Step 5: コミット**

```bash
git add docs/ARCHITECTURE.md analyzer.py tests/test_analyzer.py
git commit -m "chore: 旧analyzer.py/旧テストを削除しARCHITECTURE.mdに移行後設計書へのポインタを追記"
```

---

### Task 18: 最終検証(mypy・pytest・実グラフのE2E実行)

**Files:** なし(検証のみ)

- [ ] **Step 1: mypy 全体実行**

Run: `python3 -m mypy .`
Expected: `Success: no issues found`

- [ ] **Step 2: pytest 全体実行**

Run: `python3 -m pytest -v`
Expected: 全件 PASS。件数の目安: `test_parsing.py`(9件)+ `test_generate.py`(7件)+ `test_evaluate.py`(9件)+ `test_ranking.py`(4件)+ `test_state.py`(5件)+ `test_article_analysis.py`(5件)+ `test_dispatch.py`(4件)= 約43件

- [ ] **Step 3: .env の GEMINI_API_KEY を確認**

Run: `cat .env | grep GEMINI_API_KEY`
Expected: 有効なAPIキーが設定されていること。設定されていない場合はユーザーに確認する(実APIを叩くE2E実行が必要なため)。

- [ ] **Step 4: 実グラフをE2E実行**

Run: `python3 main.py`
Expected:
- コンソールに `leanshift-trend-bot | LangGraph版` の見出しとユーザーステータスが表示される
- 12件(4ソース×3件)の記事が並列fan-out分析され、ランク順に結果が表示される
- `N/12 件処理成功` の行が表示される(すべて成功していればN=12)
- `outputs/YYYY-MM-DD_trends.md` が保存される
- リポジトリ直下に `checkpoints.sqlite` が作成される

- [ ] **Step 5: 生成されたレポートを確認**

Run: `cat outputs/$(date +%Y-%m-%d)_trends.md | head -50`
Expected: 各記事に「要約」「Zenn構成案」「マネタイズアイデア」「X投稿下書き」のセクションが含まれ、`rank` が1から連番で振られている

- [ ] **Step 6: LangGraph Studio用グラフの疎通確認(任意)**

Run: `pip install langgraph-cli && langgraph dev --config langgraph.json` (ローカルサーバーが起動すればOK。Ctrl+Cで停止してよい)
Expected: エラーなくサーバーが起動し、ブラウザで `leanshift_trend_bot` グラフが可視化できる

- [ ] **Step 7: 完了報告**

すべてのステップがPASSしたら、ユーザーに以下を報告する:
- mypy・pytestが全件成功したこと
- 実際にE2E実行して `outputs/` にレポートが生成されたことと処理成功件数
- LangGraph Studioでグラフが可視化できたか(Step 6を実施した場合)

---

## 改訂履歴

- 2026-08-14: 初版作成。
