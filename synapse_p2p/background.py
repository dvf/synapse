import asyncio

from loguru import logger

from synapse_p2p.types import BackgroundTask


class BackgroundTaskHandler:
    def __init__(self) -> None:
        self.tasks: list[BackgroundTask] = []
        self._running: set[asyncio.Task] = set()
        self._scheduled: set[asyncio.TimerHandle] = set()
        self._started = False

    def add_task(self, task: BackgroundTask) -> None:
        self.tasks.append(task)

    async def _run(self, task: BackgroundTask) -> None:
        try:
            await task.callable()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Background task {!r} raised", task.name)

    def _schedule(self, task: BackgroundTask) -> None:
        if not self._started:
            return

        # Keep a strong reference so the task isn't garbage-collected mid-run
        # (https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task).
        running = asyncio.create_task(self._run(task), name=task.name)
        self._running.add(running)
        running.add_done_callback(self._running.discard)

        handle: asyncio.TimerHandle | None = None

        def schedule_next() -> None:
            if handle is not None:
                self._scheduled.discard(handle)
            self._schedule(task)

        handle = asyncio.get_running_loop().call_later(task.period, schedule_next)
        self._scheduled.add(handle)

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for task in self.tasks:
            self._schedule(task)

    async def stop(self) -> None:
        self._started = False
        for handle in self._scheduled:
            handle.cancel()
        self._scheduled.clear()

        for task in self._running:
            task.cancel()
        if self._running:
            await asyncio.gather(*self._running, return_exceptions=True)
        self._running.clear()
