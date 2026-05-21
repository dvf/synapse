import asyncio
from typing import Any

import pytest

from synapse_p2p import cli


class FakeLive:
    instances: list["FakeLive"] = []

    def __init__(self, renderable: Any, *, refresh_per_second: int, screen: bool) -> None:
        self.renderable = renderable
        self.refresh_per_second = refresh_per_second
        self.screen = screen
        self.updates: list[Any] = []
        FakeLive.instances.append(self)

    def __enter__(self) -> "FakeLive":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        return None

    def update(self, renderable: Any) -> None:
        self.updates.append(renderable)


@pytest.mark.asyncio
async def test_watch_uses_rich_live_alternate_screen(monkeypatch):
    FakeLive.instances.clear()
    monkeypatch.setattr(cli, "Live", FakeLive)

    task = asyncio.create_task(
        cli._watch(
            "foo.electron.network",
            "default",
            "watcher",
            [],
            False,
            True,
            0.01,
            False,
        )
    )
    await asyncio.sleep(0.03)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert FakeLive.instances
    live = FakeLive.instances[0]
    assert live.screen is True
    assert live.updates
    assert isinstance(live.updates[-1], cli.Layout)
    assert live.updates[-1]["swarm"] is not None
    assert live.updates[-1]["chatter"] is not None
