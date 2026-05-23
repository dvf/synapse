import asyncio

from examples.stock_trading_team.common import SWARM, seed
from synapse_p2p import Node, Peer

node = Node(
    name="news-observer",
    role="news observer",
    swarm=SWARM,
    capabilities=["news", "sentiment"],
    seeds=[seed()],
    heartbeat_interval=5,
    peer_timeout=20,
)

node.artifact(
    "agent-card",
    {
        "name": node.name,
        "role": node.role,
        "capabilities": ["news", "sentiment"],
        "description": "Wades into trading conversations with mock headline sentiment.",
    },
    mime_type="application/vnd.synapse.agent-card+json",
)


@node.on("peer.joined")
async def joined(peer: Peer) -> None:
    print(f"found: {peer.name}")


@node.ask
async def observe_news(task: str, context: dict) -> dict:
    symbol = context.get("symbol", "NVDA")
    return {
        "from": node.name,
        "symbol": symbol,
        "answer": (
            f"Mock news for {symbol}: product demand looks constructive; "
            "no major negative headline."
        ),
        "sentiment": "positive",
        "confidence": 0.58,
    }


async def main() -> None:
    await node.start()
    try:
        await node.join()
        print(f"news observer online at {node.address}:{node.port}")
        await asyncio.Event().wait()
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
