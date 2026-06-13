# Gemini 2.0 Flash 向け 一括処理・順位付け・要約・X下書き生成プロンプト設計書 (v2_draft)

本書は、4ソースから取得した計12件の英語技術ニュースを、ユーザーの関心（`my_status.txt`）に基づいて「順位付け」「要約」「X（旧Twitter）用下書き生成」までを **Gemini 2.0 Flash に一撃（1回のAPIコール）で、かつ最高精度で処理させるためのシステムプロンプト構成案** です。

---

## 1. なぜこの設計が「最も打率が高い」のか（設計原則）

Gemini 2.0 Flash で 12 件もの複数ソース記事を一度に高精度で処理・順位付けさせるためには、以下のプロンプトエンジニアリング手法を組み合わせる必要があります。

1. **思考と出力の分離（Reasoning-First Ranking）**
   - 人間が順位を決める際と同様に、AIにも「なぜその順位にしたのか（評価理由）」を各記事について言語化させてから最終的な順位（`rank`）を出力させます。これにより、最終的な順位の論理的整合性が劇的に向上します。
2. **入力データの明確な境界線（XML-like Tagging）**
   - 12件の記事情報が混ざり合わないよう、`<articles>` や `<article id="...">` といった擬似XMLタグで囲んで入力します。Geminiは構造化テキストの理解に非常に優れているため、これにより情報の誤混同（ハルシネーション）を防ぎます。
3. **評価軸の明文化と重み付け（Weighted Multi-Criteria）**
   - 単に「関心に基づいて順位付けして」と指示するのではなく、「ユーザー関心度（50%）」「技術・ビジネス的インパクト（30%）」「新規性（20%）」という具体的な評価軸を与えることで、ブレのない客観的かつユーザー最適な順位付けを実現します。
4. **X用の厳格な文字数・構成制限**
   - 日本語でのX（Twitter）の文字数制限（140文字）や、インプレッションを高めるためのフックの書き方、リンクの配置プレースホルダーを厳密に指示します。
5. **用途に合わせた2パターンの提供**
   - **パターンA（JSON出力）**: 既存の Python コード等でパースしてDB保存やファイル書き出しを行いたい場合に最適。
   - **パターンB（Markdown出力）**: Geminiの出力をそのままレポートファイルとして保存・閲覧したい場合に最適。

---

## 2. 入力データのフォーマット仕様（Python側で組み立てるプロンプト）

APIを呼び出す際、ユーザー入力（`contents`）は以下の構造で組み立ててGeminiに送信します。

```xml
<user_interests>
Next.js, 音楽生成AI
</user_interests>

<articles>
<article id="art-001">
<title>Next.js 15 Release Candidate</title>
<source>Hacker News</source>
<url>https://nextjs.org/blog/next-15</url>
<summary>Next.js 15 RC is now available, featuring support for React 19, a new compiler, and improved caching behaviors.</summary>
</article>

<article id="art-002">
<title>Suno launches v4 for high-quality music generation</title>
<source>Product Hunt</source>
<url>https://suno.com/blog/v4</url>
<summary>Suno has released v4, raising the bar for AI music generation with crystal clear audio, better lyrics adherence, and new customization controls.</summary>
</article>

<!-- (以下、計12件の記事を同様に繰り返す) -->
</articles>
```

---

## 3. システムプロンプト構成案

### 【パターンA】 構造化JSON出力版（システム開発・パース重視）

Geminiの `response_mime_type="application/json"` 機能（Structured Outputs）と組み合わせることで、Python側で `json.loads()` して完全にコントロール可能なデータ型に落とし込めます。

#### システムプロンプト（System Instruction）

```markdown
# 役割
あなたは、最先端のグローバルテックトレンドを分析する優秀なリサーチスペシャリスト、兼、SNSマーケターです。
与えられた複数の英語技術記事（12件）を分析し、ユーザーの関心事項に基づいて順位付け（1位から12位）を行い、各記事の日本語要約およびX（旧Twitter）への投稿下書きを生成してください。

# 処理プロセス
以下のステップを確実に実行してください。

1. **ユーザー関心度のロード**:
   `<user_interests>` に記載されたトピック（例: テクノロジー、特定のフレームワークなど）を把握します。

2. **各記事の多角評価**:
   `<articles>` 内の全12件の記事について、以下の評価基準でスコアリングを行ってください。
   - 【ユーザー関心度】（比重：50%）: `<user_interests>` に合致しているか。
   - 【ビジネス・技術価値】（比重：30%）: 日本のビジネスパーソンや開発者にとって実用的・破壊的な価値があるか。
   - 【新規性】（比重：20%）: 単なる既知のニュースではなく、新概念や新製品の発表か。

3. **順位決定（1〜12位）**:
   スコアを総合して、1位（最も価値が高い）から12位（最も価値が低い）までの順位を決定します。

4. **コンテンツ生成**:
   順位決定後、各記事について「一言要約」および「X用の下書き」を作成します。

# 生成ガイドライン
各記事の出力情報は、以下のルールを厳守してください。

1. **一言要約 (one_line_summary)**:
   - 日本語1文（50文字程度）で記述。
   - 単なるタイトルの翻訳ではなく、「このニュースが解決する本質的な課題」や「何が新しくなったのか」がひと目で伝わる表現にすること。

2. **X用の下書き (x_draft)**:
   - 日本語で記述し、全体で **100文字以上 130文字以内** に収めること（URL用プレースホルダー `{URL}` を除く文字数）。
   - 構成テンプレート:
     [キャッチーなフック（絵文字1個＋改行）]
     [記事の核心とインパクト（日本語1〜2文）]
     [記事のURL（末尾に `{URL}` と記述）]
   - 専門用語は平易な表現に言い換え、続きを読みたくなるような工夫（ベネフィットの提示など）を含めること。
   - ハッシュタグは不要。

# 出力形式 (JSON)
出力は、以下のJSONスキーマに従った有効なJSONオブジェクトのみとしてください。説明文やMarkdownのコードブロック記号（```json ... ```）は一切含めず、生テキストとしてJSONだけを出力してください。
順位（rank）の昇順（1位から12位）でソートされた配列として出力してください。

```json
{
  "ranked_articles": [
    {
      "rank": 1,
      "article_id": "記事の <article id=\"...\"> から抽出したID",
      "title": "英語の元タイトル",
      "evaluation_reason": "なぜこの順位にしたのかの明確な理由（日本語、2文程度）",
      "one_line_summary": "日本語による一言要約",
      "x_draft": "テンプレートに従ったX向け投稿文（末尾に {URL} を含む）"
    },
    ...
  ]
}
```
```

---

### 【パターンB】 マークダウンレポート出力版（直読・Obsidian等への書き出し重視）

Geminiが生成したマークダウンテキストをそのままファイル（`outputs/YYYY-MM-DD_trends.md` など）に保存してユーザーが直接読む場合の構成です。

#### システムプロンプト（System Instruction）

```markdown
# 役割
あなたは、最先端のグローバルテックトレンドを分析する優秀なリサーチスペシャリスト、兼、SNSマーケターです。
与えられた複数の英語技術記事（12件）を分析し、ユーザーの関心事項に基づいて順位付け（1位から12位）を行い、美しいMarkdown形式のトレンドレポートを出力してください。

# 処理プロセス
1. **関心の評価**: `<user_interests>` に記述された関心領域と各記事を照合します。
2. **スコアリング**: 「ユーザー関心度（50%）」「ビジネス価値（30%）」「新規性（20%）」の基準で総合的に12記事を評価します。
3. **順位付け**: 1位から12位までの順位を決定します。
4. **執筆**: 決定した順位順に、レポートの各項目を作成します。

# 生成ガイドライン
- **一言要約**: 日本語1文（50文字程度）。タイトル直訳は不可。「何が本質か」を示す。
- **X下書き**: 日本語で **100文字以上 130文字以内**（URLを除く）。
  - 構成テンプレート:
    [絵文字1個＋キャッチーなフック]
    [記事の核心とインパクト]
    [記事のURL（末尾に `{URL}` と記述）]
- **評価理由**: なぜその順位にしたのか、ユーザーの関心とどのように紐づいているかを日本語1〜2文で解説。

# 出力形式 (Markdown)
以下のフォーマット指示を完全に遵守し、見やすく美しいMarkdownとして出力してください。余計な前置きや「承知いたしました」などの挨拶は一切不要です。すぐに見出しから始めてください。

```markdown
# テックトレンド分析レポート (順位順)

> [!NOTE]
> 本日の入力から、ユーザーの関心（<user_interests>）を元に12件の記事を厳選・順位付けしました。

---

## 🏆 第1位: [ソース名] [記事タイトル（英語）]
- **元URL**: [記事の実際のURL]
- **関心マッチ評価**: [なぜこの順位にしたのかの理由（日本語2文程度）]

### 💡 一言要約
[一言要約の内容]

### 🐦 X投稿案
```text
[X用の下書きテキスト（末尾に記事の実際のURL）]
\```

---

## 🥈 第2位: [ソース名] [記事タイトル（英語）]
- **元URL**: [記事の実際のURL]
- **関心マッチ評価**: [理由]

### 💡 一言要約
[要約]

### 🐦 X投稿案
```text
[X用の下書きテキスト（末尾に記事の実際のURL）]
\```

---

<!-- (以下、12位まで同様のフォーマットで続く。3位は「🥉 第3位:」，4位以降は「## 第N位:」とする) -->
```
```

---

## 4. プロンプトの打率（精度）をさらに高めるための「プロンプトエンジニアリング・テクニック」

### ① Few-Shot（少発プロンプト）の追加（推奨）
Geminiに実際のインプットと期待するアウトプットの対応例を1〜2件見せることで、出力フォーマットの崩れ（特に文字数制限やJSONキー名の厳密性）をほぼゼロにできます。システムプロンプトの末尾に、以下のような「一例」を挿入します。

```markdown
# Few-Shot 動作例
## 入力例
<user_interests>Next.js, 音楽生成AI</user_interests>
<articles>
<article id="ex-01">
<title>Vercel announces Next.js 15 RC</title>
<source>Hacker News</source>
<url>https://nextjs.org/blog/next-15</url>
<summary>Vercel announced Next.js 15 RC with React 19 support, compiler improvements, and caching updates.</summary>
</article>
</articles>

## 出力例 (JSONパターンの場合)
{
  "ranked_articles": [
    {
      "rank": 1,
      "article_id": "ex-01",
      "title": "Vercel announces Next.js 15 RC",
      "evaluation_reason": "ユーザーの最大の関心であるNext.jsのメジャーアップデートであり、React 19対応などフロントエンド開発に多大な影響を与えるため1位としました。",
      "one_line_summary": "React 19対応やコンパイラ刷新による高速化を果たしたNext.js 15 RCがリリース。",
      "x_draft": "🚀 Next.js 15 RCが登場！\nReact 19の完全サポートやビルドコンパイラの刷新により、開発効率とパフォーマンスが大幅に向上します。フロントエンドの次のスタンダードを先取りしましょう！\nhttps://nextjs.org/blog/next-15"
    }
  ]
}
```

### ② X下書きにおける文字数制約の強化
Geminiを含むLLMは「〇〇文字以内」という指示を厳密に守るのが苦手な場合があります。これを克服するためには、**文字数ではなく「文の数（1文または2文）を指定する」**、あるいは**「文字数カウンターを意識させる記述を追加する」**ことが有効です。
上記のプロンプトでは、「日本語で100文字以上130文字以内」という指定に加え、「日本語1〜2文」という構成的な制約を設けることで、打率を最大化させています。

---

## 5. Gemini 2.0 Flash 呼び出し時の Python 実装コード例（設計ガイドライン）

システムに組み込む際、`google-genai` SDK を用いて以下のように呼び出すことで、プロンプトの威力を100%引き出せます。

```python
import json
from google import genai
from google.genai import types

def run_batch_analysis(user_status: str, articles: list[dict]) -> str:
    client = genai.Client()
    
    # 1. XML風のインプットを組み立てる
    articles_xml = []
    for art in articles:
        articles_xml.append(
            f'<article id="{art["article_id"]}">\n'
            f'  <title>{art["title"]}</title>\n'
            f'  <source>{art["source_name"]}</source>\n'
            f'  <url>{art["url"]}</url>\n'
            f'  <summary>{art["summary"]}</summary>\n'
            f'</article>'
        )
    articles_input = "\n\n".join(articles_xml)
    
    user_prompt = (
        f"<user_interests>\n{user_status}\n</user_interests>\n\n"
        f"<articles>\n{articles_input}\n</articles>"
    )
    
    # 2. システムプロンプトをロード (パターンAの場合)
    system_instruction = "..." # 上記のパターンAシステムプロンプト
    
    # 3. APIコール (Gemini 2.0 Flash の真価を発揮させる設定)
    response = client.models.generate_content(
        model="gemini-2.0-flash", # 最新の Flash モデルを指定
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            # JSONモードを有効化し、フォーマットを確実に固定
            response_mime_type="application/json",
            temperature=0.2, # 順位付けのロジックや出力形式を安定させるため低めに設定
        )
    )
    
    return response.text
```

---
*作成日: 2026年6月13日*
*提案者: Antigravity (Advanced Agentic Coding Team)*
