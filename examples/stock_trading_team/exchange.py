import asyncio
import random
from datetime import datetime

from examples.stock_trading_team.common import MARKET_TZ, SWARM, market_is_open
from synapse_p2p import Node, NodeKind, Peer

exchange = Node(
    name="paper-exchange",
    kind=NodeKind.BOOTSTRAP,
    role="exchange api",
    swarm=SWARM,
    port=9100,
    capabilities=["quotes", "paper-orders", "market-status"],
    heartbeat_interval=5,
    peer_timeout=20,
)

PRICES = {"NVDA": 128.40, "AAPL": 212.10, "TSLA": 177.20}
ORDERS: list[dict] = []

exchange.artifact(
    "agent-card",
    {
        "name": exchange.name,
        "role": exchange.role,
        "capabilities": ["quotes", "paper-orders", "market-status"],
        "description": (
            "Dumb paper exchange API. It exposes data and accepts orders; "
            "it does not trade."
        ),
    },
    mime_type="application/vnd.synapse.agent-card+json",
)


@exchange.on("peer.joined")
async def joined(peer: Peer) -> None:
    print(f"joined: {peer.name} at {peer.address}:{peer.port}")


@exchange.endpoint("exchange.market_status", description="Return paper market status")
async def market_status() -> dict:
    now = datetime.now(MARKET_TZ)
    return {"open": market_is_open(now), "time": now.isoformat(), "tz": str(MARKET_TZ)}


@exchange.endpoint("exchange.quote", description="Return a paper quote")
async def quote(symbol: str = "NVDA") -> dict:
    base = PRICES.get(symbol.upper(), 100.0)
    price = round(base + random.uniform(-1.5, 1.5), 2)
    return {"symbol": symbol.upper(), "price": price, "currency": "USD"}


@exchange.endpoint("exchange.order", description="Place a paper order")
async def order(symbol: str, side: str, quantity: int, reason: str) -> dict:
    ticket = {
        "id": f"paper-{len(ORDERS) + 1}",
        "symbol": symbol.upper(),
        "side": side.upper(),
        "quantity": quantity,
        "reason": reason,
        "accepted": True,
    }
    ORDERS.append(ticket)
    print(f"order: {ticket}")
    return ticket


async def main() -> None:
    await exchange.start()
    try:
        print(f"paper exchange listening on {exchange.address}:{exchange.port}")
        print("start analyst.py, news_observer.py, then trader.py")
        await asyncio.Event().wait()
    finally:
        await exchange.stop()


if __name__ == "__main__":
    asyncio.run(main())
