import asyncio
from asyncio import DatagramProtocol

from loguru import logger

from synapse_p2p.gossip.messages import network_message


class GossipProtocol(DatagramProtocol):
    def __init__(self):
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    @staticmethod
    def datagram_received(data, address, **kwargs):
        parsed = network_message.parse(data)
        logger.info(f"Received message from {address[0]}:{address[1]}")
        logger.info(parsed)


async def main():
    loop = asyncio.get_running_loop()

    transport, protocol = await loop.create_datagram_endpoint(lambda: GossipProtocol(), local_addr=('127.0.0.1', 9999))

    transport.close()


if __name__ == "__main__":
    asyncio.run(main())
