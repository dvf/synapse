import asyncio

import msgpack
from loguru import logger

from electron import __logo__
from electron.exceptions import InvalidMessageError
from electron.messages import RemoteProcedureCall
from electron.types import Node, build_node_from_peer_name


class Server:

    def __init__(self, address="127.0.0.1", port="9999"):
        self.address = address
        self.port = port
        self.endpoint_directory = {}
        self.max_upload_size = 4096

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
            rpc: RemoteProcedureCall = self.parse_message(data)

            endpoint = self.endpoint_directory.get(rpc.endpoint)
            if not endpoint:
                raise InvalidMessageError

            response = await endpoint(*rpc.args, rpc=rpc, node=node)
            writer.write(response.encode("utf8"))

        except InvalidMessageError:
            logger.debug(f"Invalid message received", extra={"ip": node.ip, "port": node.port, "raw": data})
            writer.write("400".encode())

        await writer.drain()

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

        async with server:
            await server.serve_forever()

    @staticmethod
    def parse_message(data: bytes):
        unpacked = msgpack.unpackb(data, raw=False)
        if not isinstance(unpacked, dict):
            raise InvalidMessageError("Received data could not be deserialized")

        if not unpacked.get("endpoint"):
            raise InvalidMessageError("Received data did not contain an RPC name")

        try:
            rpc = RemoteProcedureCall.hydrate(unpacked)
        except TypeError as e:
            raise InvalidMessageError("Received data is not a valid RPC") from e

        return rpc

    def endpoint(self, name=None, **options):
        """
        Decorator to mark a method as a UDP Endpoint
        """

        def decorator(wrapped):
            self.endpoint_directory[name or wrapped.__name__] = wrapped
            return wrapped

        return decorator

    @staticmethod
    def background(period, **options):
        """
        Decorator to schedule a background task periodically
        """

        def decorator(wrapped):
            loop = asyncio.get_event_loop()

            def c():
                asyncio.ensure_future(wrapped())
                loop.call_later(period, c)

            c()
            return wrapped

        return decorator
