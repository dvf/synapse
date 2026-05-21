import asyncio
from typing import Any

import pytest
from zeroconf import ServiceStateChange

from synapse_p2p import cli
from synapse_p2p.mdns import SERVICE_TYPE


class FakeInfo:
    properties = {
        b"swarm": b"foo.electron.network",
        b"team": b"default",
        b"name": b"alpha",
    }


class FakeAsyncZeroconf:
    def __init__(self) -> None:
        self.zeroconf = object()

    async def async_get_service_info(self, service_type: str, name: str, timeout: int = 1000):
        return FakeInfo()

    async def async_close(self) -> None:
        return None


class FakeBrowser:
    def __init__(
        self,
        zeroconf: Any,
        service_type: str,
        handlers: list,
        delay: int = 10000,
    ) -> None:
        assert delay == 0
        handler = handlers[0]
        handler(
            zeroconf=zeroconf,
            service_type=service_type,
            name="alpha._synapse._tcp.local.",
            state_change=ServiceStateChange.Added,
        )


@pytest.mark.asyncio
async def test_list_swarms_accepts_zeroconf_keyword_callback(monkeypatch):
    output: list[str] = []
    monkeypatch.setattr(cli, "AsyncZeroconf", FakeAsyncZeroconf)
    monkeypatch.setattr(cli, "AsyncServiceBrowser", FakeBrowser)
    monkeypatch.setattr(cli.typer, "echo", output.append)

    await cli._list_swarms(0.01)
    await asyncio.sleep(0)

    assert any("foo.electron.network" in line for line in output)
    assert "  - alpha" in output
    assert SERVICE_TYPE == "_synapse._tcp.local."
