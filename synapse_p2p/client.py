import asyncio

from synapse_p2p.framing import read_frame, write_frame
from synapse_p2p.messages import RPCRequest, RPCResponse
from synapse_p2p.network import connect_address
from synapse_p2p.serializers import BaseRPCSerializer, MessagePackRPCSerializer
from synapse_p2p.types import Peer
from synapse_p2p.utils import random_hash


class Client:
    def __init__(
        self,
        address: str = "127.0.0.1",
        port: int = 9999,
        serializer_class: type[BaseRPCSerializer] = MessagePackRPCSerializer,
        max_download_size: int = 4096,
        timeout: float | None = 30,
    ) -> None:
        self.address = connect_address(address)
        self.port = port
        self.serializer_class = serializer_class
        self.max_download_size = max_download_size
        self.timeout = timeout

    @classmethod
    def from_peer(
        cls,
        peer: Peer,
        *,
        serializer_class: type[BaseRPCSerializer] = MessagePackRPCSerializer,
        max_download_size: int = 4096,
        timeout: float | None = 30,
    ) -> "Client":
        return cls(
            peer.address,
            peer.port,
            serializer_class=serializer_class,
            max_download_size=max_download_size,
            timeout=timeout,
        )

    async def call(self, endpoint: str, *args, **kwargs):
        request = RPCRequest(id=random_hash(), endpoint=endpoint, args=list(args), kwargs=kwargs)
        reader, writer = await asyncio.open_connection(self.address, self.port)
        try:
            await write_frame(writer, self.serializer_class.serialize(request))
            payload = await asyncio.wait_for(
                read_frame(reader, self.max_download_size), self.timeout
            )
            response = self.serializer_class.deserialize(payload)
            if not isinstance(response, RPCResponse):
                raise RuntimeError("node returned a non-response message")
            if not response.ok:
                message = response.error.message if response.error else "RPC call failed"
                raise RuntimeError(message)
            return response.result
        finally:
            writer.close()
            await writer.wait_closed()

    async def peers(self) -> list[Peer]:
        result = await self.call("_synapse.peers")
        if not isinstance(result, list):
            raise RuntimeError("node returned an invalid peer list")
        return [Peer.from_dict(peer) for peer in result]
