import asyncio
import time
from collections import defaultdict
from typing import Annotated, Any

import typer
from rich.layout import Layout
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf

from synapse_p2p import Broadcast, BroadcastReply, Node, Peer
from synapse_p2p.mdns import SERVICE_TYPE
from synapse_p2p.node import Seed

app = typer.Typer(
    name="sn",
    help="Watch, inspect, and speak to Synapse swarms.",
    no_args_is_help=True,
)

OFFLINE_PEER_RETENTION = 180
CHATTER_LIMIT = 80


def _parse_seed(seed: list[str] | None) -> list[Seed]:
    return list(seed or [])


def _online_dot(
    last_seen: float,
    timeout: float,
    *,
    offline: bool = False,
    pulse_window: float = 0.25,
) -> str:
    if offline:
        return "[red]●[/]"
    age = time.time() - last_seen
    if age <= pulse_window:
        return "[bold bright_green]●[/]"
    if age <= timeout:
        return "[green3]●[/]"
    return "[yellow]●[/]"


def _short_nonce(nonce: str) -> str:
    return nonce.split("-", 1)[0]


def _format_result(result: Any) -> str:
    if isinstance(result, dict):
        source = result.get("from")
        answer = result.get("answer")
        if source and answer:
            return f"{source}: {answer}"
        if answer:
            return str(answer)
    return str(result)


def _event(kind: str, text: str) -> str:
    styles = {
        "joined": "bold white on dark_green",
        "heartbeat": "grey50 on grey15",
        "offline": "bold white on dark_red",
        "message": "bold white on purple4",
        "reply": "bold black on bright_cyan",
    }
    labels = {
        "joined": "JOINED",
        "heartbeat": "BEAT",
        "offline": "OFFLINE",
        "message": "ASK",
        "reply": "REPLY",
    }
    style = styles.get(kind, "bold white on grey23")
    label = labels.get(kind, kind.upper())
    pill = f"[{style}] {label:^7} [/]"
    body = f"[grey50]{escape(text)}[/]" if kind == "heartbeat" else escape(text)
    return f"{pill} {body}"


def _peer_addr(peer: Peer) -> str:
    return f"{peer.address}:{peer.port}"


def _peer_name(peer: Peer) -> str:
    return peer.name or peer.id[:8]


def _peer_label(peer: Peer) -> str:
    return f"{_peer_name(peer)} @ {_peer_addr(peer)}"


def _peer_line(
    peer: Peer,
    *,
    capabilities: bool,
    timeout: float = 20,
    offline: bool = False,
    pulse_window: float = 0.4,
    pulse_until: float | None = None,
) -> str:
    pulsing = pulse_until is not None and time.time() <= pulse_until
    last_seen = time.time() if pulsing else peer.last_seen
    dot = _online_dot(last_seen, timeout, offline=offline, pulse_window=pulse_window)
    name = escape(f"{_peer_name(peer):<16}")
    address = escape(f"{_peer_addr(peer):<21}")
    kind = escape(peer.node_kind.value)
    caps = ""
    if capabilities and peer.capabilities:
        caps = f" [dim]caps={escape(','.join(peer.capabilities))}[/]"
    return f"{dot} [bold]{name}[/] [cyan]{address}[/] [dim]{kind}[/]{caps}"


def _swarm_label(swarm: str | None, team: str | None) -> str:
    if team and team != "default":
        return f"{swarm or '-'} / {team}"
    return swarm or "-"


def _swarm_text(
    node: Node,
    *,
    capabilities: bool,
    events: list[str],
    peers: dict[str, Peer] | None = None,
    offline_peer_ids: set[str] | None = None,
    pulse_until: dict[str, float] | None = None,
) -> str:
    visible_peers = peers if peers is not None else node.peers
    offline_ids = offline_peer_ids or set()
    pulses = pulse_until or {}
    lines = [
        f"[bold]watching[/] [cyan]{escape(_swarm_label(node.swarm, node.team))}[/]",
        f"[green3]●[/] self: [bold]{escape(node.name or node.node_id[:8])}[/] "
        f"@ [cyan]{escape(f'{node.address}:{node.port}')}[/]",
        "",
    ]

    if visible_peers:
        lines.append("[bold]peers[/]")
        for peer in sorted(visible_peers.values(), key=lambda item: item.name or item.id):
            lines.append(
                _peer_line(
                    peer,
                    capabilities=capabilities,
                    timeout=node.peer_timeout,
                    offline=peer.id in offline_ids,
                    pulse_until=pulses.get(peer.id),
                )
            )
    else:
        lines.append("[dim]peers: none yet[/]")

    if events:
        lines.extend(["", "events:", *events[-8:]])

    lines.extend(["", "[dim]press Ctrl+C to stop[/]"])
    return "\n".join(lines)


def _chatter_text(events: list[str]) -> str:
    if not events:
        return "quiet so far"
    return "\n".join(events[-CHATTER_LIMIT:])


def _render_watch(
    node: Node,
    *,
    capabilities: bool,
    events: list[str],
    peers: dict[str, Peer] | None = None,
    offline_peer_ids: set[str] | None = None,
    pulse_until: dict[str, float] | None = None,
) -> Layout:
    layout = Layout(name="watch")
    layout.split_row(
        Layout(
            Panel(
                _swarm_text(
                    node,
                    capabilities=capabilities,
                    events=[],
                    peers=peers,
                    offline_peer_ids=offline_peer_ids,
                    pulse_until=pulse_until,
                ),
                title="[bold cyan]swarm[/]",
                border_style="cyan",
            ),
            name="swarm",
            ratio=1,
        ),
        Layout(
            Panel(_chatter_text(events), title="[bold magenta]chatter[/]", border_style="magenta"),
            name="chatter",
            ratio=1,
        ),
    )
    return layout


def _render_swarm(
    node: Node,
    *,
    capabilities: bool,
    events: list[str],
    peers: dict[str, Peer] | None = None,
    offline_peer_ids: set[str] | None = None,
    pulse_until: dict[str, float] | None = None,
) -> Layout:
    return _render_watch(
        node,
        capabilities=capabilities,
        events=events,
        peers=peers,
        offline_peer_ids=offline_peer_ids,
        pulse_until=pulse_until,
    )


async def _watch(
    swarm: str,
    team: str,
    name: str,
    seeds: list[Seed],
    mdns: bool,
    capabilities: bool,
    interval: float,
    show_heartbeats: bool,
) -> None:
    node = Node(
        name=name,
        role="observer",
        swarm=swarm,
        team=team,
        capabilities=["watch"],
        seeds=seeds,
        mdns=mdns,
        heartbeat_interval=2,
        peer_timeout=6,
    )
    events: list[str] = []
    seen_peers: dict[str, Peer] = {}
    offline_peer_ids: set[str] = set()
    offline_since: dict[str, float] = {}
    pulse_until: dict[str, float] = {}

    @node.endpoint("synapse.message", description="Receive a CLI swarm message")
    async def receive(message: str, broadcast: Broadcast) -> dict[str, str]:
        events.append(
            _event("message", f"{broadcast.nonce} from {_peer_label(broadcast.origin)}: {message}")
        )
        await node.reply(broadcast, {"received_by": node.name})
        return {"ok": "true"}

    @node.on("peer.joined")
    async def joined(peer: Peer) -> None:
        seen_peers[peer.id] = peer
        offline_peer_ids.discard(peer.id)
        offline_since.pop(peer.id, None)
        pulse_until[peer.id] = time.time() + 0.4
        events.append(_event("joined", _peer_label(peer)))

    @node.on("peer.heartbeat")
    async def heartbeat(peer: Peer) -> None:
        seen_peers[peer.id] = peer
        offline_peer_ids.discard(peer.id)
        offline_since.pop(peer.id, None)
        pulse_until[peer.id] = time.time() + 0.4
        if show_heartbeats:
            events.append(_event("heartbeat", f"{_peer_name(peer)}  {_peer_addr(peer)}"))

    @node.on("peer.offline")
    async def offline(peer: Peer) -> None:
        seen_peers[peer.id] = peer
        offline_peer_ids.add(peer.id)
        offline_since[peer.id] = time.time()
        pulse_until.pop(peer.id, None)
        events.append(_event("offline", _peer_label(peer)))

    @node.on("broadcast.received")
    async def broadcast_received(event: dict[str, Any]) -> None:
        broadcast = event["broadcast"]
        args = " ".join(str(arg) for arg in event.get("args", []))
        text = (
            f"{_short_nonce(broadcast.nonce)}  {_peer_name(broadcast.origin)} → "
            f"{event['endpoint']}: {args}"
        )
        events.append(_event("message", text))

    @node.on("broadcast.reply")
    async def reply(reply: BroadcastReply) -> None:
        text = (
            f"{_short_nonce(reply.nonce)}  {_peer_name(reply.peer)} → "
            f"{_format_result(reply.result)}"
        )
        events.append(_event("reply", text))

    await node.start()
    await node.join()
    try:
        with Live(
            _render_swarm(
                node,
                capabilities=capabilities,
                events=events,
                peers=seen_peers,
                offline_peer_ids=offline_peer_ids,
                pulse_until=pulse_until,
            ),
            refresh_per_second=8,
            screen=True,
        ) as live:
            while True:
                now = time.time()
                expired = [
                    peer_id
                    for peer_id, since in offline_since.items()
                    if now - since > OFFLINE_PEER_RETENTION
                ]
                for peer_id in expired:
                    offline_since.pop(peer_id, None)
                    offline_peer_ids.discard(peer_id)
                    seen_peers.pop(peer_id, None)

                live.update(
                    _render_swarm(
                        node,
                        capabilities=capabilities,
                        events=events,
                        peers=seen_peers,
                        offline_peer_ids=offline_peer_ids,
                        pulse_until=pulse_until,
                    )
                )
                await asyncio.sleep(interval)
    finally:
        await node.stop()


@app.command()
def watch(
    swarm: Annotated[str, typer.Argument(help="Swarm name, e.g. foo.electron.network")],
    team: Annotated[
        str,
        typer.Option("--team", "-t", help="Optional subgroup inside the swarm"),
    ] = "default",
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Name for this CLI watcher"),
    ] = "watcher",
    seed: Annotated[
        list[str] | None,
        typer.Option("--seed", "-s", help="Seed node as host:port. Repeatable."),
    ] = None,
    mdns: Annotated[bool, typer.Option("--mdns/--no-mdns", help="Use local mDNS discovery")] = True,
    capabilities: Annotated[
        bool,
        typer.Option("--capabilities/--no-capabilities", help="Show peer capabilities"),
    ] = True,
    interval: Annotated[
        float,
        typer.Option("--interval", help="Refresh interval in seconds"),
    ] = 0.5,
    show_heartbeats: Annotated[
        bool,
        typer.Option("--show-heartbeats", help="Show heartbeat events in chatter"),
    ] = False,
) -> None:
    """Watch a swarm in real time."""
    asyncio.run(
        _watch(swarm, team, name, _parse_seed(seed), mdns, capabilities, interval, show_heartbeats)
    )


async def _broadcast(
    swarm: str,
    team: str,
    message: str,
    name: str,
    seeds: list[Seed],
    mdns: bool,
    discover: float,
    timeout: float | None,
) -> None:
    loopback_only = bool(seeds) and all(seed[0].startswith("127.") for seed in seeds) and not mdns
    node = Node(
        name=name,
        role="speaker",
        swarm=swarm,
        team=team,
        capabilities=["broadcast"],
        seeds=seeds,
        mdns=mdns,
        bind="127.0.0.1" if loopback_only else "0.0.0.0",
        advertise="127.0.0.1" if loopback_only else "auto",
    )
    replies: asyncio.Queue[BroadcastReply] = asyncio.Queue()

    @node.on("broadcast.reply")
    async def on_reply(reply: BroadcastReply) -> None:
        await replies.put(reply)

    await node.start()
    await node.join()
    await asyncio.sleep(discover)

    broadcast = await node.broadcast("synapse.message", message)
    typer.echo(f"broadcast: {broadcast.nonce}")
    typer.echo("waiting for replies... press Ctrl+C to stop")

    try:
        while True:
            try:
                if timeout is None:
                    reply = await replies.get()
                else:
                    reply = await asyncio.wait_for(replies.get(), timeout=timeout)
            except TimeoutError:
                if not node.replies(broadcast):
                    typer.echo("no replies")
                return

            if reply.nonce == broadcast.nonce:
                typer.echo(f"- {reply.peer.name or reply.peer.id[:8]}: {reply.result}")
    finally:
        await node.stop()


@app.command("broadcast")
def broadcast_command(
    swarm: Annotated[str, typer.Argument(help="Swarm name")],
    message: Annotated[str, typer.Argument(help="Message to broadcast")],
    team: Annotated[
        str,
        typer.Option("--team", "-t", help="Optional subgroup inside the swarm"),
    ] = "default",
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Name for this CLI node"),
    ] = "speaker",
    seed: Annotated[
        list[str] | None,
        typer.Option("--seed", "-s", help="Seed node as host:port. Repeatable."),
    ] = None,
    mdns: Annotated[bool, typer.Option("--mdns/--no-mdns", help="Use local mDNS discovery")] = True,
    discover: Annotated[
        float,
        typer.Option("--discover", help="Seconds to discover peers before broadcasting"),
    ] = 0.5,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Stop after this many seconds without a reply"),
    ] = 30,
    forever: Annotated[
        bool,
        typer.Option("--forever", help="Keep streaming replies until Ctrl+C"),
    ] = False,
) -> None:
    """Broadcast a message to known swarm peers."""
    stream_timeout = None if forever else timeout
    asyncio.run(
        _broadcast(swarm, team, message, name, _parse_seed(seed), mdns, discover, stream_timeout)
    )


async def _list_swarms(seconds: float) -> None:
    found: dict[tuple[str, str], set[str]] = defaultdict(set)
    zeroconf = AsyncZeroconf()

    async def collect(service_type: str, name: str) -> None:
        info = await zeroconf.async_get_service_info(service_type, name, timeout=1000)
        if info is None:
            return
        props = info.properties or {}
        swarm = _decode(props.get(b"swarm")) or "-"
        team = _decode(props.get(b"team")) or "-"
        node_name = _decode(props.get(b"name")) or _decode(props.get(b"id"))[:8]
        found[(swarm, team)].add(node_name)

    def on_change(
        zeroconf: Any,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        if state_change in {ServiceStateChange.Added, ServiceStateChange.Updated}:
            asyncio.create_task(collect(service_type, name))

    AsyncServiceBrowser(zeroconf.zeroconf, SERVICE_TYPE, handlers=[on_change], delay=0)
    await asyncio.sleep(seconds)
    await zeroconf.async_close()

    if not found:
        typer.echo("no local Synapse swarms found")
        return

    for (swarm, team), nodes in sorted(found.items()):
        typer.echo(f"{_swarm_label(swarm, team)}  ({len(nodes)} nodes)")
        for node in sorted(nodes):
            typer.echo(f"  - {node}")


def _decode(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode()
    return value


@app.command("list-swarms")
def list_swarms(
    seconds: Annotated[float, typer.Option("--seconds", "-s", help="mDNS scan duration")] = 3,
) -> None:
    """List swarms visible on the local network via mDNS."""
    asyncio.run(_list_swarms(seconds))


if __name__ == "__main__":
    app()
