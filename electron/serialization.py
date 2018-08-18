from dataclasses import dataclass, asdict

import msgpack


def pack(obj: dataclass):
    return msgpack.packb(asdict(obj))


def unpack(packed_obj: str):
    return msgpack.unpackb(packed_obj, raw=False)


def hydrate(obj: dataclass, data: dict):
    return obj(**data)
