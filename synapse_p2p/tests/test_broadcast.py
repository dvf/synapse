import asyncio

import pytest

from synapse_p2p import Broadcast, BroadcastReply, Client, Node


@pytest.mark.asyncio
async def test_broadcast_delivers_typed_broadcast_and_collects_later_reply():
    origin = Node(
        name="origin",
        role="coordinator",
        swarm="foo.electron.network",
        team="foo",
        address="127.0.0.1",
        heartbeat_interval=None,
    )
    worker = Node(
        name="worker",
        role="worker",
        swarm="foo.electron.network",
        team="foo",
        address="127.0.0.1",
        heartbeat_interval=None,
    )
    reply_received = asyncio.Event()

    @origin.on("broadcast.reply")
    async def on_reply(reply: BroadcastReply) -> None:
        assert reply.peer.name == "worker"
        reply_received.set()

    @worker.endpoint("team.question")
    async def answer(question: str, broadcast: Broadcast) -> dict:
        await worker.reply(broadcast, {"answer": f"worker heard: {question}"})
        return {"accepted": True, "nonce": broadcast.nonce}

    await origin.start()
    await worker.start()
    origin.add_peer(worker.self_peer())

    try:
        broadcast = await origin.broadcast("team.question", "who can help?")
        await asyncio.wait_for(reply_received.wait(), 0.2)
        replies = origin.replies(broadcast)

        assert isinstance(broadcast, Broadcast)
        assert broadcast.origin.name == "origin"
        assert replies[0].nonce == broadcast.nonce
        assert replies[0].result == {"answer": "worker heard: who can help?"}
    finally:
        await worker.stop()
        await origin.stop()


@pytest.mark.asyncio
async def test_broadcast_reply_endpoint_validates_membership():
    origin = Node(
        swarm="foo.electron.network",
        team="foo",
        address="127.0.0.1",
        heartbeat_interval=None,
    )
    tcp = await origin.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    try:
        with pytest.raises(RuntimeError, match="different swarm"):
            await Client(host, port).call(
                "_synapse.broadcast.reply",
                "nonce",
                {
                    "id": "bad",
                    "name": "bad",
                    "address": "127.0.0.1",
                    "port": 9999,
                    "swarm": "bar.electron.network",
                    "team": "foo",
                    "kind": "node",
                },
                result={"answer": "nope"},
            )
    finally:
        await origin.stop()
