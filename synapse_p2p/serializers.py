from dataclasses import asdict, is_dataclass

import msgpack
from loguru import logger

from synapse_p2p.exceptions import InvalidMessageError
from synapse_p2p.messages import RPCError, RPCRequest, RPCResponse

RPCMessage = RPCRequest | RPCResponse


class BaseRPCSerializer:
    @classmethod
    def serialize(cls, outgoing: RPCMessage) -> bytes:
        raise NotImplementedError

    @classmethod
    def deserialize(cls, incoming: bytes) -> RPCMessage:
        raise NotImplementedError


class MessagePackRPCSerializer(BaseRPCSerializer):
    @classmethod
    def serialize(cls, outgoing: RPCMessage) -> bytes:
        if not is_dataclass(outgoing):
            raise TypeError("RPC messages must be dataclass instances")
        return msgpack.packb(asdict(outgoing), use_bin_type=True)

    @classmethod
    def deserialize(cls, incoming: bytes) -> RPCMessage:
        try:
            payload = msgpack.unpackb(incoming, raw=False)
            if not isinstance(payload, dict):
                raise TypeError("payload must be a map")

            message_type = payload.get("type", "request")
            if message_type == "request":
                unknown = set(payload) - {"type", "id", "endpoint", "args", "kwargs"}
                if unknown:
                    raise TypeError(f"unknown request fields: {sorted(unknown)}")
                return RPCRequest(
                    id=str(payload.get("id", "")),
                    endpoint=payload["endpoint"],
                    args=list(payload.get("args", [])),
                    kwargs=dict(payload.get("kwargs", {})),
                )

            if message_type == "response":
                unknown = set(payload) - {"type", "id", "ok", "result", "error"}
                if unknown:
                    raise TypeError(f"unknown response fields: {sorted(unknown)}")
                error = payload.get("error")
                return RPCResponse(
                    id=str(payload.get("id", "")),
                    ok=bool(payload["ok"]),
                    result=payload.get("result"),
                    error=RPCError(**error) if error is not None else None,
                )

            raise TypeError(f"unknown RPC message type: {message_type}")
        except (KeyError, TypeError, ValueError, msgpack.UnpackException) as e:
            logger.error("Could not deserialize payload: {!r}", incoming)
            raise InvalidMessageError(str(e)) from e
