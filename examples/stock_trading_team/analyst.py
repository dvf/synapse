import asyncio

from examples.stock_trading_team.common import SWARM, seed
from synapse_p2p import Node, Peer

node = Node(
    name="analyst",
    role="market analyst",
    swarm=SWARM,
    capabilities=["technical-analysis", "risk"],
    seeds=[seed()],
    heartbeat_interval=5,
    peer_timeout=20,
)

node.artifact(
    "agent-card",
    {
        "name": node.name,
        "role": node.role,
        "capabilities": ["technical-analysis", "risk"],
        "description": "Wades into trading conversations with lightweight paper analysis.",
    },
    mime_type="application/vnd.synapse.agent-card+json",
)


@node.on("peer.joined")
async def joined(peer: Peer) -> None:
    print(f"found: {peer.name}")


@node.ask
async def analyze(task: str, context: dict) -> dict:
    symbol = context.get("symbol", "NVDA")
    price = context.get("price", "unknown")
    return {
        "from": node.name,
        "symbol": symbol,
        "answer": f"At ${price}, {symbol} has momentum but keep position size small.",
        "signal": "bullish",
        "confidence": 0.62,
    }


async def main() -> None:
    await node.start()
    try:
        await node.join()
        print(f"analyst online at {node.address}:{node.port}")
        await asyncio.Event().wait()
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
