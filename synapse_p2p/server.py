import asyncio
import contextlib
from collections.abc import Callable

from loguru import logger

from synapse_p2p import __logo__
from synapse_p2p.background import BackgroundTaskHandler
from synapse_p2p.exceptions import InvalidMessageError
from synapse_p2p.messages import RemoteProcedureCall
from synapse_p2p.serializers import BaseRPCSerializer, MessagePackRPCSerializer
from synapse_p2p.types import BackgroundTask, Node, build_node_from_peer_name


class Server:
    def __init__(
        self,
        address: str = "127.0.0.1",
        port: int = 9999,
        serializer_class: type[BaseRPCSerializer] = MessagePackRPCSerializer,
        max_upload_size: int = 4096,
    ) -> None:
        self.address = address
        self.port = port
        self.endpoint_directory: dict[str, Callable] = {}
        self.max_upload_size = max_upload_size
        self.background_executor = BackgroundTaskHandler()
        self.serializer_class = serializer_class

    def run(self) -> None:
        """Run the server."""
        print(__logo__)
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(self.serve())

    async def handle_data(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Receive data, dispatch to registered endpoint, write response."""
        node: Node = build_node_from_peer_name(writer.get_extra_info("peername"))
        logger.debug("Talking to Node {} @ {}:{}", node.identifier, node.ip, node.port)

        data = await reader.read(self.max_upload_size)

        try:
            rpc: RemoteProcedureCall = self.serializer_class.deserialize(data)

            endpoint = self.endpoint_directory.get(rpc.endpoint)
            if endpoint is None:
                raise InvalidMessageError(f"Unregistered endpoint called: {rpc.endpoint}")

            result = await endpoint(*rpc.args, rpc=rpc, node=node, response=writer)
            if result is None:
                await writer.drain()
        except InvalidMessageError:
            logger.debug("Invalid message from {}:{}: {!r}", node.ip, node.port, data)
            writer.write(b"400")

        logger.debug("Closing connection to {}:{}", node.ip, node.port)
        writer.close()
        await writer.wait_closed()

    async def serve(self) -> None:
        """Attach TCP Stream handler to underlying socket interface."""
        server = await asyncio.start_server(self.handle_data, self.address, self.port)

        print(f"Listening on {self.address}:{self.port}\n")
        print("Registered Endpoints:")
        for endpoint in self.endpoint_directory:
            print(f"- {endpoint}")

        print("\nBackground Tasks:")
        for task in self.background_executor.tasks:
            print(f"- {task.name} ({task.period}s)")
        print()

        self.background_executor.start()

        async with server:
            await server.serve_forever()

    def endpoint(self, name: str | None = None) -> Callable:
        """Decorator to register a coroutine as an RPC endpoint."""

        def decorator(wrapped: Callable) -> Callable:
            self.endpoint_directory[name or wrapped.__name__] = wrapped
            return wrapped

        return decorator

    def background(self, period: float) -> Callable:
        """Decorator to schedule a coroutine as a periodic background task."""

        def decorator(wrapped: Callable) -> Callable:
            self.background_executor.add_task(
                BackgroundTask(name=wrapped.__name__, callable=wrapped, period=period)
            )
            return wrapped

        return decorator
