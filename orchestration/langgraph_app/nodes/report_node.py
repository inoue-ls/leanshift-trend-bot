from core.reporting import save_markdown_report
from orchestration.langgraph_app.state import GraphState


def report_node(state: GraphState) -> dict:
    """レポートのファイル保存のみを行う(コンソール出力はmain.pyの責務)"""
    path = save_markdown_report(state["ranked"], state["user_status"])
    return {"report_path": path}
