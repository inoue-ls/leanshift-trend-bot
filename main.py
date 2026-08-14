import asyncio
import pathlib
import sys
from datetime import date
from core.analysis.client import build_client
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
    # GEMINI_API_KEY が無い/不正な場合はここで即座に失敗させる。
    # generate_node/evaluate_node 内で呼ばれると、記事単位の broad except に
    # 飲み込まれて "0/12 件処理成功" + exit 0 という偽の部分成功に見えてしまうため、
    # 何も出力しないうちに fail-fast させる。
    build_client()

    print("[実行開始] LangGraphパイプラインを起動します...")

    user_status = load_user_status()

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

    if not final_state["ranked"] and final_state["articles"]:
        print(
            f"[エラー] {len(final_state['articles'])} 件の記事取得に成功しましたが、"
            "全記事の分析処理に失敗しました。GEMINI_API_KEY やネットワーク状態を確認してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    print(format_console_report(final_state["ranked"], user_status))
    print(f"\n{len(final_state['ranked'])}/{len(final_state['articles'])} 件処理成功")
    print(f"\n[保存完了] {final_state['report_path']}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
