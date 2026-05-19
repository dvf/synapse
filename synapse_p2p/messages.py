from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RemoteProcedureCall:
    endpoint: str
    args: list[Any] = field(default_factory=list)
