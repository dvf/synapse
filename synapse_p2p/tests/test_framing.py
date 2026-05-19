import asyncio
import struct

import pytest

from synapse_p2p.exceptions import InvalidMessageError
from synapse_p2p.framing import encode_frame, read_frame


def test_encode_frame_prefixes_payload_length():
    payload = b"hello"
    assert encode_frame(payload) == struct.pack("!I", len(payload)) + payload


@pytest.mark.asyncio
async def test_read_frame_rejects_oversized_frame():
    reader = asyncio.StreamReader()
    reader.feed_data(struct.pack("!I", 10) + b"0123456789")
    reader.feed_eof()

    with pytest.raises(InvalidMessageError, match="frame too large"):
        await read_frame(reader, max_size=5)


@pytest.mark.asyncio
async def test_read_frame_rejects_incomplete_frame():
    reader = asyncio.StreamReader()
    reader.feed_data(struct.pack("!I", 10) + b"short")
    reader.feed_eof()

    with pytest.raises(InvalidMessageError, match="incomplete frame"):
        await read_frame(reader, max_size=20)
