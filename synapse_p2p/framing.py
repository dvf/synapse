import asyncio
import struct

from synapse_p2p.exceptions import InvalidMessageError

_HEADER = struct.Struct("!I")


async def read_frame(reader: asyncio.StreamReader, max_size: int) -> bytes:
    try:
        header = await reader.readexactly(_HEADER.size)
        (size,) = _HEADER.unpack(header)
        if size > max_size:
            raise InvalidMessageError(f"frame too large: {size} > {max_size}")
        return await reader.readexactly(size)
    except asyncio.IncompleteReadError as e:
        raise InvalidMessageError("incomplete frame") from e


def encode_frame(payload: bytes) -> bytes:
    return _HEADER.pack(len(payload)) + payload


async def write_frame(writer: asyncio.StreamWriter, payload: bytes) -> None:
    writer.write(encode_frame(payload))
    await writer.drain()
