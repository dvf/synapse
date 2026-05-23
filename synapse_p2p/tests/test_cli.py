import time

import pytest

from synapse_p2p import Broadcast, Node, Peer
from synapse_p2p.cli import (
    CHATTER_LIMIT,
    OFFLINE_PEER_RETENTION,
    _ask,
    _broadcast,
    _chatter_text,
    _format_result,
    _loopback_only,
    _parse_key_value,
    _parse_seed,
    _peer_label,
    _peer_line,
    _short_nonce,
    _swarm_label,
    _swarm_text,
)


def test_parse_seed_defaults_to_empty_list():
    assert _parse_seed(None) == []


def test_parse_key_value_context():
    assert _parse_key_value(["diff=abc", "url=https://example.com"]) == {
        "diff": "abc",
        "url": "https://example.com",
    }


def test_loopback_only_supports_string_and_tuple_seeds():
    assert _loopback_only(["127.0.0.1:9999", ("127.0.0.1", 8888)], mdns=False) is True
    assert _loopback_only(["192.168.1.10:9999"], mdns=False) is False
    assert _loopback_only(["127.0.0.1:9999"], mdns=True) is False


def test_offline_peer_retention_is_a_few_minutes():
    assert OFFLINE_PEER_RETENTION == 180


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

    assert "watching" in text
    assert "foo.electron.network" in text
    assert "self:" in text
    assert "reviewer" in text
    assert "127.0.0.1:8888" in text
    assert "caps=code-review" in text
    assert "joined: reviewer" in text
    assert "\033" not in text



def test_peer_label_includes_name_ip_and_port():
    peer = Peer(id="peer-1", name="reviewer", address="127.0.0.1", port=9999)

    assert _peer_label(peer) == "reviewer @ 127.0.0.1:9999"


def test_event_uses_readable_pill_label():
    from synapse_p2p.cli import _event

    text = _event("joined", "reviewer @ 127.0.0.1:9999")

    assert "JOINED" in text
    assert "on dark_green" in text


def test_chatter_helpers_compact_nonce_and_result():
    assert _short_nonce("019e4ab0-1d0d-709a") == "019e4ab0"
    assert _format_result({"from": "coder", "answer": "I can implement it."}) == (
        "coder: I can implement it."
    )


def test_chatter_text_shows_recent_events():
    events = [f"event {index}" for index in range(CHATTER_LIMIT + 5)]

    text = _chatter_text(events)

    assert f"event {CHATTER_LIMIT + 4}" in text
    assert "event 0" not in text


def test_peer_line_shows_stale_dot_after_timeout():
    peer = Peer(
        id="peer-1",
        name="reviewer",
        address="127.0.0.1",
        port=9999,
        last_seen=time.time() - 60,
    )

    assert _peer_line(peer, capabilities=False, timeout=20).startswith("[yellow]●[/]")
    assert _peer_line(peer, capabilities=False, timeout=20, offline=True).startswith("[red]●[/]")


def test_peer_line_pulses_after_recent_heartbeat():
    peer = Peer(
        id="peer-1",
        name="reviewer",
        address="127.0.0.1",
        port=9999,
        last_seen=time.time(),
    )

    assert _peer_line(peer, capabilities=False).startswith("[bold bright_green]●[/]")
    assert _peer_line(peer, capabilities=False, pulse_window=0).startswith("[green3]●[/]")


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
        bind="127.0.0.1",
        advertise="127.0.0.1",
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
            [("127.0.0.1", port)],
            False,
            0,
            1,
        )
    finally:
        await worker.stop()

    assert any(line.startswith("broadcast: ") for line in output)
    assert any("worker" in line and "heard hello" in line for line in output)
    assert "no replies" not in output


@pytest.mark.asyncio
async def test_cli_ask_streams_acks_and_replies_from_seed_peer(monkeypatch):
    output: list[str] = []
    worker = Node(
        name="worker",
        swarm="foo.electron.network",
        bind="127.0.0.1",
        advertise="127.0.0.1",
        heartbeat_interval=None,
    )

    @worker.ask
    async def handle(task: str, context: dict):
        return {"answer": f"handled {task} with {context['kind']}"}

    listener = await worker.start()
    _host, port = listener.sockets[0].getsockname()[:2]
    monkeypatch.setattr("synapse_p2p.cli.typer.echo", output.append)

    try:
        await _ask(
            "foo.electron.network",
            "default",
            "review this",
            "asker",
            [("127.0.0.1", port)],
            False,
            0,
            1,
            {"kind": "diff"},
        )
    finally:
        await worker.stop()

    assert any(line.startswith("ask: ") for line in output)
    assert any("worker acked" in line for line in output)
    assert any("worker" in line and "handled review this with diff" in line for line in output)
    assert "no replies" not in output


@pytest.mark.asyncio
async def test_cli_ask_times_out_cleanly_without_replies(monkeypatch):
    output: list[str] = []
    monkeypatch.setattr("synapse_p2p.cli.typer.echo", output.append)

    await _ask(
        "foo.electron.network",
        "default",
        "hello",
        "asker",
        [],
        False,
        0,
        0.01,
    )

    assert any(line.startswith("ask: ") for line in output)
    assert "no replies" in output


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
