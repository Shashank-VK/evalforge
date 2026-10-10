import asyncio
import sqlite3
from typing import Callable, Any
from evalforge.logger import get_logger

logger = get_logger(__name__)

class WriteJob:
    def __init__(self, fn: Callable[[sqlite3.Connection], Any], future: asyncio.Future):
        self.fn = fn
        self.future = future

class AsyncWriterQueue:
    """Serialized async writer queue for SQLite.
    Guarantees that all write transactions run serially on a single dedicated connection,
    completely preventing database locks under high async concurrency.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._queue: asyncio.Queue[WriteJob | None] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._conn: sqlite3.Connection | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        from evalforge.storage.db import get_connection
        self._conn = get_connection(self.db_path)
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        while self._running:
            job = await self._queue.get()
            if job is None:
                self._queue.task_done()
                break
            try:
                if self._conn is None:
                    from evalforge.storage.db import get_connection
                    self._conn = get_connection(self.db_path)
                result = job.fn(self._conn)
                self._conn.commit()
                if not job.future.done():
                    job.future.set_result(result)
            except Exception as e:
                if self._conn:
                    try:
                        self._conn.rollback()
                    except Exception:
                        pass
                if not job.future.done():
                    job.future.set_exception(e)
            finally:
                self._queue.task_done()

    async def execute_write(self, fn: Callable[[sqlite3.Connection], Any]) -> Any:
        """Enqueues a write function and awaits its completion."""
        if not self._running:
            self.start()
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        job = WriteJob(fn, future)
        await self._queue.put(job)
        return await future

    async def stop(self) -> None:
        """Stops the worker cleanly after draining pending writes."""
        if not self._running:
            return
        await self._queue.put(None)
        if self._worker_task:
            await self._worker_task
        self._running = False
        if self._conn:
            self._conn.close()
            self._conn = None
