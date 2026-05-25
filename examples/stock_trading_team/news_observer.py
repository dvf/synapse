import asyncio
import random
from typing import Any

from examples.stock_trading_team.common import SWARM, seed
from synapse_p2p import Node, Peer, every

HEADLINES: list[dict[str, Any]] = [
    {
        "headline": "Nvidia data-center demand remains strong, analysts say",
        "sentiment": "positive",
        "confidence": 0.67,
    },
    {
        "headline": "Cloud buyers are reportedly negotiating harder on GPU pricing",
        "sentiment": "neutral",
        "confidence": 0.51,
    },
    {
        "headline": "New export restrictions could pressure Nvidia's China revenue",
        "sentiment": "negative",
        "confidence": 0.61,
    },
    {
        "headline": "Major hyperscaler announces expanded Nvidia accelerator deployment",
        "sentiment": "positive",
        "confidence": 0.72,
    },
    {
        "headline": "Semiconductor supply chain checks look stable for the quarter",
        "sentiment": "positive",
        "confidence": 0.56,
    },
]

latest_story = random.choice(HEADLINES)

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
        "description": "Periodically watches mock Nvidia headlines and shares sentiment.",
    },
    mime_type="application/vnd.synapse.agent-card+json",
)


@node.on("peer.joined")
async def joined(peer: Peer) -> None:
    print(f"found: {peer.name}")


@node.periodic(every(seconds=15))
async def watch_nvidia_news() -> None:
    global latest_story
    latest_story = random.choice(HEADLINES)
    print(
        "news tick: "
        f"{latest_story['headline']} "
        f"({latest_story['sentiment']}, confidence={latest_story['confidence']})"
    )


@node.ask
async def observe_news(task: str, context: dict) -> dict:
    symbol = context.get("symbol", "NVDA")
    if symbol != "NVDA":
        return {
            "from": node.name,
            "symbol": symbol,
            "answer": "I am only watching Nvidia news in this demo.",
            "sentiment": "neutral",
            "confidence": 0.2,
        }

    return {
        "from": node.name,
        "symbol": symbol,
        "answer": f"Latest Nvidia headline: {latest_story['headline']}",
        "sentiment": latest_story["sentiment"],
        "confidence": latest_story["confidence"],
    }


async def main() -> None:
    await node.start()
    try:
        await node.join()
        print(f"news observer online at {node.address}:{node.port}")
        print("watching mock Nvidia headlines every 15 seconds")
        await asyncio.Event().wait()
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
