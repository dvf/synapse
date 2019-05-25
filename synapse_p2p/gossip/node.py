import asyncio
from asyncio import DatagramProtocol
from signal import SIGINT, SIGTERM
from loguru import logger


class GossipProtocol(DatagramProtocol):
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.transport = None

    def __call__(self, host, port):
        self.transport, _ = self.loop.run_until_complete(
            self.loop.create_datagram_endpoint(lambda: self, (host, port))
        )
        self.loop.create_task(self.find_peers())

    def connection_made(self, transport):
        self.transport = transport

    def stop(self):
        logger.info("Gracefully exiting...")
        self.transport.close()
        self.loop.stop()

    @staticmethod
    def datagram_received(data, address, **kwargs):
        logger.info(f"Received message from {address[0]}:{address[1]}")
        logger.info(data)
        # parsed = network_message.parse(data)
        # logger.info(parsed)

    @staticmethod
    async def find_peers():
        while True:
            print("finding peers")
            await asyncio.sleep(5)
        # task = asyncio.create_task(find_peers(loop))


gs = GossipProtocol()
gs("127.0.0.1", 9999)

loop = asyncio.get_event_loop()
loop.add_signal_handler(SIGINT, gs.stop)
loop.add_signal_handler(SIGTERM, gs.stop)

loop.run_forever()


