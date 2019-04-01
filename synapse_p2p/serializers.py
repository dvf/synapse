from dataclasses import asdict

import msgpack
from loguru import logger

from synapse_p2p import RemoteProcedureCall
from synapse_p2p.exceptions import InvalidMessageError


class BaseRPCSerializer:
    def serialize(self, outgoing: dict) -> bytes:
        raise NotImplementedError

    def deserialize(self, incoming: bytes) -> dict:
        raise NotImplementedError


class MessagePackRPCSerializer(BaseRPCSerializer):
    @classmethod
    def serialize(cls, outgoing: RemoteProcedureCall) -> bytes:
        return msgpack.packb(asdict(outgoing))

    @classmethod
    def deserialize(cls, incoming: bytes) -> RemoteProcedureCall:
        try:
            return RemoteProcedureCall(**msgpack.unpackb(incoming, raw=False))
        except TypeError as e:
            logger.error(f"Could not deserialize payload to dataclass", bytes)
            raise InvalidMessageError from e
