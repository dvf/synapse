import struct
from dataclasses import asdict, dataclass

import msgpack
from loguru import logger

from synapse_p2p import RemoteProcedureCall
from synapse_p2p.exceptions import InvalidMessageError


class BaseSerializer:
    @classmethod
    def serialize(cls, outgoing: RemoteProcedureCall) -> bytes:
        raise NotImplementedError

    @classmethod
    def deserialize(cls, incoming: bytes) -> RemoteProcedureCall:
        raise NotImplementedError


class MessagePackRPCSerializer(BaseSerializer):
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


class BitcoinSerializer(BaseSerializer):
    @classmethod
    def deserialize(cls, incoming: bytes) -> RemoteProcedureCall:
        pass

    @classmethod
    def serialize(cls, outgoing: RemoteProcedureCall) -> bytes:
        message_name = getattr(self, "MESSAGE_NAME")
        payload = getattr(self, "serialize")()

        # magic value for Main net
        magic = bytes.fromhex("F9BEB4D9")
        command = message_name + (12 - len(message_name)) * "\00"
        length = s.pack("<I", len(payload))

        # Bitcoin checksums only use the first 4 bytes
        checksum = sha256(sha256(payload).digest()).digest()[:4]

        return magic + command.encode() + length + checksum + payload


class SerializerException(Exception):
    pass


class Field:
    def dump(self, value: bytes) -> bytes:
        raise NotImplementedError("Must implement `dump`")

    def load(self, value: bytes) -> bytes:
        raise NotImplementedError("Must implement `load`")


class ByteField(Field):
    def __init__(self, byte_format, size, default=None, strip_null_bytes=True):
        self.byte_format = byte_format
        self.size = size
        self.default = default
        self.strip_null_bytes = strip_null_bytes

    def dump(self, value: bytes):
        if len(value) > self.size:
            raise SerializerException("Length too long")

        return struct.pack(self.byte_format, value or self.default)

    def load(self, value: bytes):
        if len(value) > self.size:
            raise SerializerException("Length too long")

        p = struct.unpack(self.byte_format, self.size)[0]

        return p.split(b'\0', 1)[0] if self.strip_null_bytes is True else p


class VarStrField(Field):
    def __init__(self, byte_format, size, default=None, strip_null_bytes=True):
        self.byte_format = byte_format
        self.size = size
        self.default = default
        self.strip_null_bytes = strip_null_bytes

    def serialize_var_int(i: int) -> bytes:
        stream = bytes()

        if i < 0:
            raise ValueError("var_int can't be negative")
        elif i < 0xfd:
            stream += bytes([i])
        elif i <= 0xffff:
            stream += bytes([0xfd])
            stream += struct.pack(b'<H', i)
        elif i <= 0xffffffff:
            stream += bytes([0xfe])
            stream += struct.pack(b'<I', i)
        else:
            stream += bytes([0xff])
            stream += struct.pack(b'<Q', i)

        return stream

    def deserialize_var_int(stream: bytes) -> Tuple[int, bytes]:
        i = stream[0]
        if i < 0xfd:
            return i, stream[1:]
        elif i == 0xfd:
            return struct.unpack(b'<H', stream[1:3])[0], stream[3:]
        elif i == 0xfe:
            return struct.unpack(b'<I', stream[1:5])[0], stream[5:]
        else:
            return struct.unpack(b'<Q', stream[1:9])[0], stream[9:]


class Version(BitcoinSerializer):
    services = ByteField("<Q", size=8, default=0)
    ip = ByteField("<16s", size=16)
    port = ByteField("<H", size=2)

    class Meta:
        message_name = "net_addr"
