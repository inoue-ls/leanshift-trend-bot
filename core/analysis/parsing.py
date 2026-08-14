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
