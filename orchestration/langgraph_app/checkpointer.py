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
