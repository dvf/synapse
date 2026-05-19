import asyncio
import contextlib
import inspect
from collections.abc import Callable

from loguru import logger

from synapse_p2p import __logo__
from synapse_p2p.background import BackgroundTaskHandler
from synapse_p2p.exceptions import InvalidMessageError
from synapse_p2p.framing import read_frame, write_frame
from synapse_p2p.messages import RPCError, RPCRequest, RPCResponse
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
        self._server: asyncio.Server | None = None

    def run(self) -> None:
        """Run the server."""
        print(__logo__)
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(self.serve())

    async def _dispatch(self, rpc: RPCRequest, node: Node):
        endpoint = self.endpoint_directory.get(rpc.endpoint)
        if endpoint is None:
            raise InvalidMessageError(f"Unregistered endpoint called: {rpc.endpoint}")

        signature = inspect.signature(endpoint)
        injected = {"rpc": rpc, "node": node}
        kwargs = dict(rpc.kwargs)
        for name, value in injected.items():
            if name in signature.parameters:
                kwargs[name] = value

        return await endpoint(*rpc.args, **kwargs)

    async def handle_data(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Receive a framed request, dispatch it, and write a framed response."""
        node: Node = build_node_from_peer_name(writer.get_extra_info("peername"))
        logger.debug("Talking to Node {} @ {}:{}", node.identifier, node.ip, node.port)
        request_id = ""

        try:
            data = await read_frame(reader, self.max_upload_size)
            rpc = self.serializer_class.deserialize(data)
            if not isinstance(rpc, RPCRequest):
                raise InvalidMessageError("expected request message")
            request_id = rpc.id

            result = await self._dispatch(rpc, node)
            response = RPCResponse(id=request_id, ok=True, result=result)
        except InvalidMessageError as e:
            logger.debug("Invalid message from {}:{}: {}", node.ip, node.port, e)
            response = RPCResponse(
                id=request_id,
                ok=False,
                error=RPCError(code="bad_request", message=str(e)),
            )
        except Exception as e:
            logger.exception("Endpoint raised while handling {}:{}", node.ip, node.port)
            response = RPCResponse(
                id=request_id,
                ok=False,
                error=RPCError(code="internal_error", message=str(e)),
            )

        await write_frame(writer, self.serializer_class.serialize(response))
        logger.debug("Closing connection to {}:{}", node.ip, node.port)
        writer.close()
        await writer.wait_closed()

    def _print_startup(self) -> None:
        print(f"Listening on {self.address}:{self.port}\n")
        print("Registered Endpoints:")
        for endpoint in self.endpoint_directory:
            print(f"- {endpoint}")

        print("\nBackground Tasks:")
        for task in self.background_executor.tasks:
            print(f"- {task.name} ({task.period}s)")
        print()

    async def start(self) -> asyncio.Server:
        """Start accepting connections without blocking forever."""
        if self._server is not None:
            return self._server

        self._server = await asyncio.start_server(self.handle_data, self.address, self.port)
        self.background_executor.start()
        return self._server

    async def stop(self) -> None:
        """Stop accepting connections and cancel background tasks."""
        await self.background_executor.stop()
        if self._server is None:
            return

        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def serve(self) -> None:
        """Attach TCP Stream handler to underlying socket interface."""
        server = await self.start()
        self._print_startup()

        try:
            async with server:
                await server.serve_forever()
        finally:
            await self.stop()

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
