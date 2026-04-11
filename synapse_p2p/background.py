import asyncio

from synapse_p2p.types import BackgroundTask


class BackgroundTaskHandler:
    def __init__(self) -> None:
        self.tasks: list[BackgroundTask] = []

    def add_task(self, task: BackgroundTask) -> None:
        self.tasks.append(task)

    def _schedule(self, task: BackgroundTask) -> None:
        asyncio.create_task(task.callable())
        asyncio.get_running_loop().call_later(task.period, self._schedule, task)

    def start(self) -> None:
        for task in self.tasks:
            self._schedule(task)
