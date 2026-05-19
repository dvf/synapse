import msgpack
import pytest

from synapse_p2p.exceptions import InvalidMessageError
from synapse_p2p.messages import RemoteProcedureCall
from synapse_p2p.serializers import MessagePackRPCSerializer


def test_roundtrip():
    rpc = RemoteProcedureCall(endpoint="sum", args=[1, 2, 3])
    restored = MessagePackRPCSerializer.deserialize(MessagePackRPCSerializer.serialize(rpc))
    assert restored == rpc


def test_deserialize_rejects_unknown_fields():
    payload = msgpack.packb({"endpoint": "sum", "args": [1], "bogus": True})
    assert isinstance(payload, bytes)
    with pytest.raises(InvalidMessageError):
        MessagePackRPCSerializer.deserialize(payload)


def test_deserialize_rejects_garbage_bytes():
    with pytest.raises(InvalidMessageError):
        MessagePackRPCSerializer.deserialize(b"\xff\xff\xff not msgpack")
