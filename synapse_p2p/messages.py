from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(slots=True)
class RPCError:
    code: str
    message: str


@dataclass(slots=True)
class RPCRequest:
    endpoint: str
    id: str = ""
    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)
    type: Literal["request"] = "request"


@dataclass(slots=True)
class RPCResponse:
    id: str
    ok: bool
    result: Any | None = None
    error: RPCError | None = None
    type: Literal["response"] = "response"


# Backwards-compatible alias for the original public request type.
RemoteProcedureCall = RPCRequest
