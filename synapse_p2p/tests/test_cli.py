import pytest

from synapse_p2p import Broadcast, Node, Peer
from synapse_p2p.cli import _broadcast, _parse_seed, _peer_line, _swarm_label, _swarm_text


def test_parse_seed_defaults_to_empty_list():
    assert _parse_seed(None) == []


def test_swarm_label_hides_default_team():
    assert _swarm_label("foo.electron.network", "default") == "foo.electron.network"
    assert _swarm_label("foo.electron.network", "backend") == "foo.electron.network / backend"


def test_swarm_text_contains_peers_and_recent_events_without_terminal_codes():
    node = Node(name="watcher", swarm="foo.electron.network", port=9999)
    node.add_peer(
        Peer(
            id="peer-1",
            name="reviewer",
            address="127.0.0.1",
            port=8888,
            capabilities=["code-review"],
        )
    )

    text = _swarm_text(node, capabilities=True, events=["joined: reviewer"])

    assert "watching foo.electron.network" in text
    assert "reviewer" in text
    assert "caps=code-review" in text
    assert "joined: reviewer" in text
    assert "\033" not in text



def test_peer_line_can_include_or_hide_capabilities():
    peer = Peer(
        id="peer-1",
        name="reviewer",
        address="127.0.0.1",
        port=9999,
        capabilities=["code-review", "tests"],
    )

    assert "caps=code-review,tests" in _peer_line(peer, capabilities=True)
    assert "caps=" not in _peer_line(peer, capabilities=False)


@pytest.mark.asyncio
async def test_cli_broadcast_streams_replies_from_seed_peer(monkeypatch):
    output: list[str] = []
    worker = Node(
        name="worker",
        swarm="foo.electron.network",
        address="127.0.0.1",
        heartbeat_interval=None,
    )

    @worker.endpoint("synapse.message")
    async def receive(message: str, broadcast: Broadcast) -> dict[str, str]:
        await worker.reply(broadcast, {"answer": f"heard {message}"})
        return {"ok": "true"}

    listener = await worker.start()
    host, port = listener.sockets[0].getsockname()[:2]
    monkeypatch.setattr("synapse_p2p.cli.typer.echo", output.append)

    try:
        await _broadcast(
            "foo.electron.network",
            "default",
            "hello",
            "speaker",
            [f"{host}:{port}"],
            False,
            0,
            0.2,
        )
    finally:
        await worker.stop()

    assert any(line.startswith("broadcast: ") for line in output)
    assert any("worker" in line and "heard hello" in line for line in output)
    assert "no replies" not in output


@pytest.mark.asyncio
async def test_cli_broadcast_times_out_cleanly_without_replies(monkeypatch):
    output: list[str] = []
    monkeypatch.setattr("synapse_p2p.cli.typer.echo", output.append)

    await _broadcast(
        "foo.electron.network",
        "default",
        "hello",
        "speaker",
        [],
        False,
        0,
        0.01,
    )

    assert any(line.startswith("broadcast: ") for line in output)
    assert "no replies" in output
