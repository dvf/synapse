import asyncio

import pytest

from synapse_p2p.node import Node
from synapse_p2p.periodic import PeriodicTaskHandler
from synapse_p2p.schedules import every
from synapse_p2p.types import PeriodicTask


@pytest.mark.asyncio
async def test_periodic_task_exception_does_not_stop_scheduling():
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        raise RuntimeError("boom")

    handler = PeriodicTaskHandler()
    handler.add_task(PeriodicTask(name="flaky", callable=flaky, schedule=every(seconds=0.01)))
    handler.start()

    await asyncio.sleep(0.05)

    assert calls >= 2, "scheduler should keep firing despite the task raising"


@pytest.mark.asyncio
async def test_periodic_task_holds_strong_reference_until_done():
    started = asyncio.Event()
    finish = asyncio.Event()

    async def gated():
        started.set()
        await finish.wait()

    handler = PeriodicTaskHandler()
    handler.add_task(PeriodicTask(name="gated", callable=gated, schedule=every(seconds=999)))
    handler.start()

    await started.wait()
    assert len(handler._running) == 1

    finish.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert handler._running == set()


@pytest.mark.asyncio
async def test_periodic_task_stop_cancels_future_runs():
    calls = 0

    async def tick():
        nonlocal calls
        calls += 1

    handler = PeriodicTaskHandler()
    handler.add_task(PeriodicTask(name="tick", callable=tick, schedule=every(seconds=0.01)))
    handler.start()
    await asyncio.sleep(0.02)
    await handler.stop()

    calls_after_stop = calls
    await asyncio.sleep(0.03)

    assert calls_after_stop >= 1
    assert calls == calls_after_stop


@pytest.mark.asyncio
async def test_periodic_task_added_after_start_is_scheduled():
    called = asyncio.Event()

    async def late_task():
        called.set()

    handler = PeriodicTaskHandler()
    handler.start()
    handler.add_task(
        PeriodicTask(name="late_task", callable=late_task, schedule=every(seconds=999))
    )

    await asyncio.wait_for(called.wait(), timeout=0.1)
    await handler.stop()


def test_periodic_task_rejects_non_positive_interval():
    with pytest.raises(ValueError, match="interval schedule"):
        every(seconds=0)


def test_periodic_decorator_rejects_sync_functions():
    node = Node(bind="127.0.0.1")

    with pytest.raises(TypeError, match="async function"):

        @node.periodic(1)
        def tick():
            pass
