import asyncio
from datetime import UTC, datetime

from loguru import logger

from synapse_p2p.types import PeriodicTask


class PeriodicTaskHandler:
    def __init__(self) -> None:
        self.tasks: list[PeriodicTask] = []
        self._running: set[asyncio.Task] = set()
        self._scheduled: set[asyncio.TimerHandle] = set()
        self._started = False

    def add_task(self, task: PeriodicTask) -> None:
        self.tasks.append(task)
        if self._started:
            self._schedule(task, immediate=True)

    async def _run(self, task: PeriodicTask) -> None:
        try:
            await task.callable()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Periodic task {!r} raised", task.name)

    def _schedule(self, task: PeriodicTask, *, immediate: bool = False) -> None:
        if not self._started:
            return

        delay = 0.0
        if not immediate:
            now = datetime.now(UTC)
            task.next_run = task.schedule.next_after(task.next_run or now)
            delay = max(0.0, (task.next_run - now).total_seconds())

        handle: asyncio.TimerHandle | None = None

        def run_and_schedule_next() -> None:
            if handle is not None:
                self._scheduled.discard(handle)

            # Keep a strong reference so the task isn't garbage-collected mid-run
            # (https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task).
            running = asyncio.create_task(self._run(task), name=task.name)
            self._running.add(running)
            running.add_done_callback(self._running.discard)
            self._schedule(task)

        handle = asyncio.get_running_loop().call_later(delay, run_and_schedule_next)
        self._scheduled.add(handle)

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for task in self.tasks:
            self._schedule(task, immediate=True)

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
