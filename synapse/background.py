import asyncio
import multiprocessing

from synapse.types import BackgroundTask


class BackgroundTaskHandler:
    def __init__(self, n=None):
        self.cpu_count = n or multiprocessing.cpu_count()
        self.tasks = []

    @staticmethod
    def schedule_task(coroutine: BackgroundTask):
        loop = asyncio.get_running_loop()

        # Schedule coroutine recursively
        async def c():
            await asyncio.sleep(coroutine.period)
            await coroutine.callable()
            await c()

        loop.create_task(c())

    def add_task(self, task: BackgroundTask):
        self.tasks.append(task)

    def __call__(self, *args, **kwargs):
        for task in self.tasks:
            self.schedule_task(task)
