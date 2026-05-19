import asyncio

from loguru import logger

from synapse_p2p.types import BackgroundTask


class BackgroundTaskHandler:
    def __init__(self) -> None:
        self.tasks: list[BackgroundTask] = []
        self._running: set[asyncio.Task] = set()

    def add_task(self, task: BackgroundTask) -> None:
        self.tasks.append(task)

    async def _run(self, task: BackgroundTask) -> None:
        try:
            await task.callable()
        except Exception:
            logger.exception("Background task {!r} raised", task.name)

    def _schedule(self, task: BackgroundTask) -> None:
        # Keep a strong reference so the task isn't garbage-collected mid-run
        # (https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task).
        running = asyncio.create_task(self._run(task), name=task.name)
        self._running.add(running)
        running.add_done_callback(self._running.discard)
        asyncio.get_running_loop().call_later(task.period, self._schedule, task)

    def start(self) -> None:
        for task in self.tasks:
            self._schedule(task)
