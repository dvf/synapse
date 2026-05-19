import msgpack
import pytest

from synapse_p2p import RemoteProcedureCall
from synapse_p2p.exceptions import InvalidMessageError
from synapse_p2p.messages import RPCError, RPCRequest, RPCResponse
from synapse_p2p.serializers import MessagePackRPCSerializer


def test_remote_procedure_call_alias_still_constructs_request():
    rpc = RemoteProcedureCall(endpoint="ping")
    assert isinstance(rpc, RPCRequest)
    assert rpc.endpoint == "ping"


def test_response_roundtrip():
    response = RPCResponse(id="abc", ok=True, result={"nested": [1, 2, 3]})
    restored = MessagePackRPCSerializer.deserialize(MessagePackRPCSerializer.serialize(response))
    assert restored == response


def test_error_response_roundtrip():
    response = RPCResponse(
        id="abc",
        ok=False,
        error=RPCError(code="bad_request", message="nope"),
    )
    restored = MessagePackRPCSerializer.deserialize(MessagePackRPCSerializer.serialize(response))
    assert restored == response


def test_deserialize_rejects_unknown_response_fields():
    payload = msgpack.packb({"type": "response", "id": "abc", "ok": True, "bogus": True})
    with pytest.raises(InvalidMessageError):
        MessagePackRPCSerializer.deserialize(payload)


def test_deserialize_rejects_non_map_payload():
    payload = msgpack.packb(["not", "a", "map"])
    with pytest.raises(InvalidMessageError):
        MessagePackRPCSerializer.deserialize(payload)
