from dataclasses import dataclass, asdict

import msgpack
from loguru import logger

from synapse_p2p.exceptions import InvalidMessageError


@dataclass
class MsgPackMixin:
    def encode(self):
        return msgpack.packb(asdict(self))

    @classmethod
    def hydrate(cls, payload: dict):
        try:
            return cls(**payload)
        except TypeError as e:
            logger.error(f"Could not hydrate payload to dataclass: {payload}")
            raise InvalidMessageError from e


@dataclass
class RemoteProcedureCall(MsgPackMixin):
    endpoint: str
    args: list = None
