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
