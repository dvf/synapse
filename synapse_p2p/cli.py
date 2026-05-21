import asyncio
from collections import defaultdict
from typing import Annotated, Any

import typer
from rich.live import Live
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


def _parse_seed(seed: list[str] | None) -> list[Seed]:
    return list(seed or [])


def _peer_line(peer: Peer, *, capabilities: bool) -> str:
    label = peer.name or peer.id[:8]
    caps = f" caps={','.join(peer.capabilities)}" if capabilities and peer.capabilities else ""
    return f"- {label:<16} {peer.address}:{peer.port:<5} {peer.node_kind.value}{caps}"


def _swarm_label(swarm: str | None, team: str | None) -> str:
    if team and team != "default":
        return f"{swarm or '-'} / {team}"
    return swarm or "-"


def _swarm_text(node: Node, *, capabilities: bool, events: list[str]) -> str:
    lines = [
        f"watching {_swarm_label(node.swarm, node.team)}",
        f"self: {node.name or node.node_id[:8]} @ {node.address}:{node.port}",
        "",
    ]

    if node.peers:
        lines.append("peers:")
        for peer in sorted(node.peers.values(), key=lambda item: item.name or item.id):
            lines.append(_peer_line(peer, capabilities=capabilities))
    else:
        lines.append("peers: none yet")

    if events:
        lines.extend(["", "events:", *events[-8:]])

    lines.extend(["", "press Ctrl+C to stop"])
    return "\n".join(lines)


def _render_swarm(node: Node, *, capabilities: bool, events: list[str]) -> str:
    return _swarm_text(node, capabilities=capabilities, events=events)


async def _watch(
    swarm: str,
    team: str,
    name: str,
    seeds: list[Seed],
    mdns: bool,
    capabilities: bool,
    interval: float,
) -> None:
    node = Node(
        name=name,
        role="observer",
        swarm=swarm,
        team=team,
        capabilities=["watch"],
        seeds=seeds,
        mdns=mdns,
    )
    events: list[str] = []

    @node.endpoint("synapse.message", description="Receive a CLI swarm message")
    async def receive(message: str, broadcast: Broadcast) -> dict[str, str]:
        events.append(f"message {broadcast.nonce} from {broadcast.origin.name}: {message}")
        await node.reply(broadcast, {"received_by": node.name})
        return {"ok": "true"}

    @node.on("peer.joined")
    async def joined(peer: Peer) -> None:
        events.append(f"joined: {peer.name or peer.id[:8]} @ {peer.address}:{peer.port}")

    @node.on("peer.offline")
    async def offline(peer: Peer) -> None:
        events.append(f"offline: {peer.name or peer.id[:8]}")

    @node.on("broadcast.reply")
    async def reply(reply: BroadcastReply) -> None:
        events.append(f"reply {reply.nonce} from {reply.peer.name}: {reply.result}")

    await node.start()
    await node.join()
    try:
        with Live(
            _render_swarm(node, capabilities=capabilities, events=events),
            refresh_per_second=4,
            screen=True,
        ) as live:
            while True:
                live.update(_render_swarm(node, capabilities=capabilities, events=events))
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
) -> None:
    """Watch a swarm in real time."""
    asyncio.run(_watch(swarm, team, name, _parse_seed(seed), mdns, capabilities, interval))


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
