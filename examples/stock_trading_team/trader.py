import asyncio
from typing import Any, cast

from examples.stock_trading_team.common import SWARM, seed
from synapse_p2p import BroadcastReply, Client, ConversationEvent, Node, Peer, every

node = Node(
    name="trader",
    role="paper trader",
    swarm=SWARM,
    capabilities=["trade-decision", "coordination"],
    seeds=[seed()],
    heartbeat_interval=5,
    peer_timeout=20,
)

node.artifact(
    "agent-card",
    {
        "name": node.name,
        "role": node.role,
        "capabilities": ["trade-decision", "coordination"],
        "description": (
            "Coordinates analyst/news replies during market hours "
            "and places paper orders."
        ),
    },
    mime_type="application/vnd.synapse.agent-card+json",
)


@node.on("peer.joined")
async def joined(peer: Peer) -> None:
    print(f"found: {peer.name} capabilities={peer.capabilities}")


@node.on("conversation.ack")
async def acked(event: ConversationEvent) -> None:
    print(f"ack: {event.peer.name} entered {event.conversation_id}")


async def wait_for_replies(conversation, timeout: float = 4) -> list[BroadcastReply]:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        replies = node.replies(conversation)
        if len(replies) >= 2:
            return replies
        await asyncio.sleep(0.25)
    return node.replies(conversation)


@node.periodic(every(seconds=30))
async def market_scan() -> None:
    exchange = next((peer for peer in node.peers.values() if peer.name == "paper-exchange"), None)
    if exchange is None:
        print("scan: no exchange yet")
        return

    client = Client.from_peer(exchange)
    status = cast(dict[str, Any], await client.call("exchange.market_status"))
    if not status["open"]:
        print(f"scan: market closed at {status['time']} — not spending agent tokens")
        return

    quote = cast(dict[str, Any], await client.call("exchange.quote", "NVDA"))
    print(f"scan: market open, asking swarm about {quote['symbol']} @ ${quote['price']}")

    conversation = await node.broadcast(
        "synapse.ask",
        f"Should we paper trade {quote['symbol']} right now?",
        context={
            "symbol": quote["symbol"],
            "price": quote["price"],
            "source": "trader.market_scan",
        },
    )
    replies = await wait_for_replies(conversation)
    for reply in replies:
        print(f"reply: {reply.peer.name}: {reply.result}")

    bullish = sum(1 for reply in replies if reply.result.get("signal") == "bullish")
    positive = sum(1 for reply in replies if reply.result.get("sentiment") == "positive")
    if bullish and positive:
        order = await client.call(
            "exchange.order",
            quote["symbol"],
            "buy",
            1,
            "analyst bullish + news positive in shared conversation",
        )
        print(f"paper order: {order}")
    else:
        print("decision: no trade")


async def main() -> None:
    await node.start()
    try:
        await node.join()
        print(f"trader online at {node.address}:{node.port}")
        print("periodic scan runs every 30s, but only spends tokens during market hours")
        await asyncio.Event().wait()
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
