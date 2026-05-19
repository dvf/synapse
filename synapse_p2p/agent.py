from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from synapse_p2p.server import Server

AgentTaskHandler = Callable[[str, dict[str, Any]], Awaitable[Any]]


@dataclass(slots=True)
class AgentCapability:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)


class AgentNode(Server):
    def __init__(
        self,
        *,
        name: str,
        role: str,
        description: str = "",
        capabilities: list[str | AgentCapability] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.name = name
        self.role = role
        self.description = description
        self.capabilities = [self._normalize_capability(c) for c in capabilities or []]
        self._task_handler: AgentTaskHandler | None = None
        self._register_agent_endpoints()

    def _normalize_capability(self, capability: str | AgentCapability) -> AgentCapability:
        if isinstance(capability, str):
            return AgentCapability(name=capability)
        return capability

    def capability(
        self,
        name: str,
        *,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> AgentCapability:
        capability = AgentCapability(
            name=name,
            description=description,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
        )
        self.capabilities.append(capability)
        return capability

    def task_handler(self, wrapped: AgentTaskHandler) -> AgentTaskHandler:
        self._task_handler = wrapped
        return wrapped

    def _register_agent_endpoints(self) -> None:
        @self.endpoint("_agent.info", publish=False)
        async def agent_info() -> dict[str, Any]:
            return {
                "name": self.name,
                "role": self.role,
                "description": self.description,
                "capabilities": [capability.name for capability in self.capabilities],
            }

        @self.endpoint("_agent.capabilities", publish=False)
        async def agent_capabilities() -> list[dict[str, Any]]:
            return [asdict(capability) for capability in self.capabilities]

        @self.endpoint("_agent.ask", publish=False)
        async def agent_ask(task: str, context: dict[str, Any] | None = None) -> Any:
            if self._task_handler is None:
                raise RuntimeError("agent has no task handler")
            return await self._task_handler(task, context or {})
