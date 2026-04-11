from dataclasses import asdict

import msgpack
from loguru import logger

from synapse_p2p.exceptions import InvalidMessageError
from synapse_p2p.messages import RemoteProcedureCall


class BaseRPCSerializer:
    @classmethod
    def serialize(cls, outgoing: RemoteProcedureCall) -> bytes:
        raise NotImplementedError

    @classmethod
    def deserialize(cls, incoming: bytes) -> RemoteProcedureCall:
        raise NotImplementedError


class MessagePackRPCSerializer(BaseRPCSerializer):
    @classmethod
    def serialize(cls, outgoing: RemoteProcedureCall) -> bytes:
        return msgpack.packb(asdict(outgoing))

    @classmethod
    def deserialize(cls, incoming: bytes) -> RemoteProcedureCall:
        try:
            payload = msgpack.unpackb(incoming, raw=False)
            return RemoteProcedureCall(**payload)
        except (TypeError, ValueError, msgpack.UnpackException) as e:
            logger.error("Could not deserialize payload: {!r}", incoming)
            raise InvalidMessageError(str(e)) from e
