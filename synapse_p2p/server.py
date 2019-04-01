import asyncio

from loguru import logger

from synapse_p2p import __logo__
from synapse_p2p.background import BackgroundTaskHandler
from synapse_p2p.exceptions import InvalidMessageError
from synapse_p2p.messages import RemoteProcedureCall
from synapse_p2p.serializers import MessagePackRPCSerializer
from synapse_p2p.types import Node, build_node_from_peer_name, BackgroundTask


class Server:

    def __init__(self, address="127.0.0.1", port="9999", serializer_class=MessagePackRPCSerializer):
        self.address = address
        self.port = port
        self.namespace = None
        self.endpoint_directory = {}
        self.max_upload_size = 4096
        self.background_executor = BackgroundTaskHandler()
        self.serializer_class = serializer_class
        print(__logo__)

    def run(self):
        """
        Run the server
        """
        loop = asyncio.get_event_loop()
        try:
            asyncio.ensure_future(self.serve())
            loop.run_forever()
        except KeyboardInterrupt:
            loop.stop()

    async def handle_data(self, reader, writer):
        """
        Coroutine handler for receiving data, parsing the message and returning a response
        """
        node: Node = build_node_from_peer_name(writer.get_extra_info('peername'))
        logger.debug(f"Talking to Node {node.identifier} @ {node.ip}:{node.port}")

        data = await reader.read(self.max_upload_size)

        try:
            rpc: RemoteProcedureCall = self.serializer_class.deserialize(data)

            endpoint = self.endpoint_directory.get(rpc.endpoint)
            if not endpoint:
                raise InvalidMessageError(f"Unregistered endpoint called: {rpc.endpoint}")

            r = await endpoint(*rpc.args, rpc=rpc, node=node, response=writer)
            if r is None:
                await writer.drain()

        except InvalidMessageError:
            logger.debug(f"Invalid message received", extra={"ip": node.ip, "port": node.port, "raw": data})
            writer.write("400".encode())

        logger.debug("Closing Connection")
        writer.close()

    async def serve(self):
        """
        Attach TCP Stream handler to underlying socket interface
        """
        server = await asyncio.start_server(self.handle_data, self.address, self.port)

        print(f"Listening on {self.address}:{self.port}")
        print(f"\nRegistered Endpoints:")
        for endpoint in self.endpoint_directory:
            print(f"- {endpoint}")

        print(f"\nBackground Tasks:")
        for task in self.background_executor.tasks:
            print(f"- {task.name} ({task.period}s)")

        print("\n")
        self.background_executor()

        async with server:
            await server.serve_forever()

    def endpoint(self, name=None, **options):
        """
        Decorator to mark a method as a UDP Endpoint
        """

        def decorator(wrapped):
            self.endpoint_directory[name or wrapped.__name__] = wrapped
            return wrapped

        return decorator

    def background(self, period, **options):
        """
        Decorator to schedule a background task periodically
        """

        def decorator(wrapped):
            self.background_executor.add_task(
                BackgroundTask(name=wrapped.__name__,
                               callable=wrapped,
                               period=period)
            )
            return wrapped

        return decorator
