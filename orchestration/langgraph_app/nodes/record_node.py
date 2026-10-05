import pathlib
from datetime import date
from core.run_records import RunRecord, save_run_record
from orchestration.langgraph_app.state import GraphState

RUNS_DIR = pathlib.Path("runs")


def record_node(state: GraphState) -> dict:
    """実行の記録を runs/YYYY-MM-DD.json に保存する"""
    record = RunRecord(
        run_date=date.today().isoformat(),
        articles_fetched=len(state["articles"]),
        articles=state.get("records", []),
    )
    return {"record_path": save_run_record(record, RUNS_DIR)}
