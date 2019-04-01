from dataclasses import dataclass


@dataclass
class RemoteProcedureCall:
    endpoint: str
    args: list = None
