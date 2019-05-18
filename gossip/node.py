import asyncio
from asyncio import BaseProtocol

from construct import Struct, PascalString, VarInt, Bytes, this, CString, Switch
from loguru import logger

# Messages:
# - V version
# - A agent
# - C checksum
# - S size
# - P payload
#     - I ping
#     - O pongØ
#     - G gossip

message = Struct(
    version=PascalString(VarInt, "utf8"),
    client=PascalString(VarInt, "utf8"),
    method=CString("utf8"),
    payload=Switch(this.method, {
        "ping": Bytes(0),
        "pong": Bytes(1)
    }),
)


class Protocol(BaseProtocol):
    def __init__(self):
        logger.info("Starting Protocol")
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, address):
        parsed = message.parse(data)
        logger.info(f"Received message from {address[0]}:{address[1]}")
        logger.info(parsed)


async def main():
    loop = asyncio.get_running_loop()

    transport, protocol = await loop.create_datagram_endpoint(lambda: Protocol(), local_addr=('127.0.0.1', 9999))

    try:
        await asyncio.sleep(3600)
    finally:
        transport.close()


if __name__ == "__main__":
    asyncio.run(main())
