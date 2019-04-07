import asyncio
import multiprocessing

from synapse_p2p.types import BackgroundTask


class BackgroundTaskHandler:
    def __init__(self, n=None):
        self.cpu_count = n or multiprocessing.cpu_count()
        self.tasks = []

    def schedule_task(self, background_task: BackgroundTask):
        asyncio.create_task(background_task.callable())

        # Schedule recursive background task
        asyncio.get_event_loop().call_later(
            background_task.period,
            self.schedule_task,
            background_task,
        )

    def add_task(self, task: BackgroundTask):
        self.tasks.append(task)

    def __call__(self, *args, **kwargs):
        for task in self.tasks:
            self.schedule_task(task)
