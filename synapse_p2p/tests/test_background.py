import asyncio

import pytest

from synapse_p2p.background import BackgroundTaskHandler
from synapse_p2p.types import BackgroundTask


@pytest.mark.asyncio
async def test_background_task_exception_does_not_stop_scheduling():
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        raise RuntimeError("boom")

    handler = BackgroundTaskHandler()
    handler.add_task(BackgroundTask(name="flaky", callable=flaky, period=0.01))
    handler.start()

    await asyncio.sleep(0.05)

    assert calls >= 2, "scheduler should keep firing despite the task raising"


@pytest.mark.asyncio
async def test_background_task_holds_strong_reference_until_done():
    started = asyncio.Event()
    finish = asyncio.Event()

    async def gated():
        started.set()
        await finish.wait()

    handler = BackgroundTaskHandler()
    handler.add_task(BackgroundTask(name="gated", callable=gated, period=999))
    handler.start()

    await started.wait()
    assert len(handler._running) == 1

    finish.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert handler._running == set()


@pytest.mark.asyncio
async def test_background_task_stop_cancels_future_runs():
    calls = 0

    async def tick():
        nonlocal calls
        calls += 1

    handler = BackgroundTaskHandler()
    handler.add_task(BackgroundTask(name="tick", callable=tick, period=0.01))
    handler.start()
    await asyncio.sleep(0.02)
    await handler.stop()

    calls_after_stop = calls
    await asyncio.sleep(0.03)

    assert calls_after_stop >= 1
    assert calls == calls_after_stop
