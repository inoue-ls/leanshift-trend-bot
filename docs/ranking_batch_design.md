# 一括バッチ処理・順位付け設計書 (ranking_batch_design)

本書は、`leanshift-trend-bot` の AI 解析部を「12件の記事を1件ずつループで個別にGemini APIを呼び出す構造」から、「12件の記事を1回のAPIコールで一括処理し、ユーザー関心度順にソートされた構造化JSONとして返却させる構造」へ移行するための詳細設計書です。

---

## 1. 一撃バッチ処理のためのプロンプト設計

一括処理において、Gemini に対し「12件の記事を漏れなく相互評価し、順位付きの構造化データとして返却する」ことを強制するためのプロンプトの構成設計です。

### ユーザー入力（User Content）の組み立て設計
Python 側で組み立てる入力プロンプトは、以下のように関心事と全12件の記事情報を明示的な境界線（疑似XMLタグ）で区切って一括で送信します。

```xml
<user_interests>
Next.js, 音楽生成AI, 個人開発
</user_interests>

<articles>
<article id="art-001">
  <title>[記事1のタイトル]</title>
  <source>[ソース名]</source>
  <url>[URL]</url>
  <summary>[記事1の英語本文・サマリー]</summary>
</article>
<article id="art-002">
  <title>[記事2のタイトル]</title>
  <source>[ソース名]</source>
  <url>[URL]</url>
  <summary>[記事2の英語本文・サマリー]</summary>
</article>
...
<article id="art-012">
  <title>[記事12のタイトル]</title>
  <source>[ソース名]</source>
  <url>[URL]</url>
  <summary>[記事12の英語本文・サマリー]</summary>
</article>
</articles>
```

### システムインストラクション（System Instruction）における指示設計
システムプロンプトにおいて、以下のルールを強調します。

*   **全件処理の義務付け**: 「`<articles>` 内にある12件の記事すべてを漏れなく評価し、結果に含めてください。一部の記事を省略することは認められません」と指示。
*   **IDベースの紐付け**: 「返却するJSONオブジェクトの `article_id` には、入力の `<article id="...">` で指定された値を正確にマッピングしてください」と指示。
*   **ソート順の強制**: 「`rank` は最も価値が高い記事を1とし、12までの重複のない連番にしてください。出力配列は必ず `rank` の昇順でソートしてください」と指示。

---

## 2. `analyzer.py` の関数シグネチャ案

既存の `ProcessedDraft` のデータ構造を維持しつつ、バッチ処理へ切り替えるためのシグネチャおよび内部処理の設計案です。

### 設計上の決定事項（モデル定義の維持）
`models.py` の `ProcessedDraft` は「変更不可マスター」であり、`rank`（順位）や `evaluation_reason`（評価理由）というフィールドを持っていません。
モデル定義を変更しないため、**Python側で返却するリスト（`list[ProcessedDraft]`）の「要素の並び順（インデックス順）」そのものを順位（インデックス0 = 1位、インデックス11 = 12位）として扱う**設計とします。これによりモデルの独立性を守ります。

### 新しい関数シグネチャ

```python
from google import genai
from models import RawArticle, ProcessedDraft

def analyze_articles_batch(
    articles: list[RawArticle],
    client: genai.Client | None = None,
    user_status: str = "",
) -> list[ProcessedDraft]:
    """
    12件の記事を一括で Gemini 2.0 Flash に送信し、ユーザーの関心度順に
    ソートされた ProcessedDraft のリストを返却する。
    
    Args:
        articles: 取得した生記事のリスト (通常12件)
        client: Gemini API クライアント
        user_status: my_status.txt から取得したユーザーの関心テキスト
        
    Returns:
        list[ProcessedDraft]: 関心度順（1位〜12位）に並び替えられた解析済み下書きリスト
    """
    # 1. 12件の articles から XML 文字列を一括構築
    # 2. システムプロンプトおよび Few-Shot（docs/prompt_fewshot_examples.md）の準備
    # 3. response_schema を指定して client.models.generate_content() を1回呼び出し
    # 4. 返ってきた JSON データをパース
    # 5. 各要素から ProcessedDraft を生成し、順位（rank）の昇順でソートしたリストを返却
```

---

## 3. Gemini が返す JSON のスキーマ定義

Gemini 2.0 Flash の **Structured Outputs（構造化出力）** 機能を利用し、出力を 100% 正確にバリデーションするための Pydantic スキーマ定義です。

### API パラメータに渡すスキーマ定義 (Python)

```python
from pydantic import BaseModel, Field

class RankedArticleJSON(BaseModel):
    rank: int = Field(
        ..., 
        description="1から始まる重複のない順位。1が最もユーザー関心度およびビジネス価値が高い。"
    )
    article_id: str = Field(
        ..., 
        description="入力の <article id=\"...\"> タグで指定された一意のID。"
    )
    title: str = Field(
        ..., 
        description="記事の英語元タイトル。"
    )
    evaluation_reason: str = Field(
        ..., 
        description="この順位となった根拠。ユーザー関心トピックとの関連性を交えて日本語2文程度で記述。"
    )
    one_line_summary: str = Field(
        ..., 
        description="日本語による一言要約（50文字程度）。解決する本質を記述。"
    )
    background_analysis: str = Field(
        ..., 
        description="なぜ海外で流行しているかの背景（日本語、3〜5文程度）。"
    )
    zenn_article_structure: str = Field(
        ..., 
        description="Zenn記事にする場合のタイトル案と見出し構成（日本語、改行区切り）。"
    )
    monetization_idea: str = Field(
        ..., 
        description="日本市場向けローカライズビジネスモデル（日本語）。"
    )
    x_post_draft: str = Field(
        ..., 
        description="X投稿用下書き（日本語、100〜130文字、末尾に {URL} を含む）。"
    )

class BatchAnalysisResponse(BaseModel):
    ranked_articles: list[RankedArticleJSON] = Field(
        ..., 
        description="順位（rank）の昇順でソートされた全記事のリスト。"
    )
```

API呼び出し時に `config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=BatchAnalysisResponse)` と指定することで、Geminiはこの通りの型でデータを返却します。

---

## 4. API コスト・パフォーマンス比較

12件の記事を処理する際、「個別ループ処理（12回）」と「一撃バッチ処理（1回）」のコストおよび実行速度の比較です。

### 前提条件（トークン数算出の想定値）
*   **システムプロンプト**: 約 800 トークン
*   **Few-Shot（5件のデモ）**: 約 2,000 トークン（一括処理時のフォーマット安定用）
*   **ユーザーステータス**: 約 50 トークン
*   **生記事1件の情報**: 入力約 200 トークン
*   **解析結果1件の情報**: 出力約 500 トークン
*   **Gemini 2.0 Flash 料金**: 入力: \$0.075 / 1M tokens、出力: \$0.30 / 1M tokens

### コスト・トークンシミュレーション

| 項目 | 現状：個別呼び出し（12回） | 提案：バッチ呼び出し（1回） | 差分 / メリット |
| :--- | :--- | :--- | :--- |
| **APIコール回数** | 12回 | **1回** | **API接続オーバーヘッドが1/12に激減** |
| **入力トークン計算** | (システム800 + 関心50 + 記事200) × 12<br>= **12,600 tokens** | システム800 + FewShot2000 + 関心50 + (記事200 × 12)<br>= **5,250 tokens** | **入力トークン数を58%削減**<br>(共通のシステム指示文等を重複送信しないため) |
| **出力トークン計算** | 結果500 × 12<br>= **6,000 tokens** | (結果500 × 12) + スキーマ枠100<br>= **6,100 tokens** | ほぼ同等 |
| **API費用 (USD)** | 入力: \$0.000945<br>出力: \$0.001800<br>合計: **\$0.002745** | 入力: \$0.000393<br>出力: \$0.001830<br>合計: **\$0.002223** | **約19%の費用削減**<br>(入力トークン削減効果による) |
| **処理時間 (目安)** | 約 20 〜 25 秒<br>(直列ループ処理の場合) | **約 5 〜 8 秒** | **約 3倍の高速化**<br>(並列処理不要で速度向上) |
| **順位付けの精度** | **不可**（記事の関連性を個別にしか見られない） | **極めて高い**（全12件の全容を把握して相対評価） | **一括バッチ呼び出しの最大の強み** |

### 比較結果まとめ
一括バッチ処理に切り替えることで、**費用を約 20% 削減**し、**処理速度を 3倍高速化**しつつ、**個別処理では実現不可能な「全記事を並べた高精度な相対ランキング」** を実現することができます。

---
*作成日: 2026年6月13日*
*提案者: Antigravity (Advanced Agentic Coding Team)*
