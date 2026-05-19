
import pytest

from synapse_p2p import AgentCapability, AgentNode, Client


@pytest.mark.asyncio
async def test_agent_info_and_capabilities_are_discoverable():
    agent = AgentNode(
        name="Reviewer",
        role="reviewer",
        description="Reviews Python code",
        capabilities=[
            "python",
            AgentCapability(name="code-review", description="Review code for quality"),
        ],
        address="127.0.0.1",
        port=0,
    )

    server = await agent.start()
    host, port = server.sockets[0].getsockname()[:2]

    try:
        client = Client(host, port)
        assert await client.call("_agent.info") == {
            "name": "Reviewer",
            "role": "reviewer",
            "description": "Reviews Python code",
            "capabilities": ["python", "code-review"],
        }
        assert await client.call("_agent.capabilities") == [
            {"name": "python", "description": "", "input_schema": {}, "output_schema": {}},
            {
                "name": "code-review",
                "description": "Review code for quality",
                "input_schema": {},
                "output_schema": {},
            },
        ]
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_agent_ask_delegates_to_task_handler():
    agent = AgentNode(name="Coder", role="coder", capabilities=["python"], port=0)

    @agent.task_handler
    async def handle_task(task: str, context: dict):
        return {"task": task, "language": context["language"]}

    server = await agent.start()
    host, port = server.sockets[0].getsockname()[:2]

    try:
        result = await Client(host, port).call(
            "_agent.ask", "write a test", context={"language": "python"}
        )
        assert result == {"task": "write a test", "language": "python"}
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_published_methods_excludes_private_system_and_agent_endpoints():
    agent = AgentNode(name="Coder", role="coder", port=0)

    @agent.endpoint("public.tool", description="A public tool")
    async def public_tool():
        return "ok"

    @agent.endpoint("private.tool", publish=False)
    async def private_tool():
        return "hidden"

    server = await agent.start()
    host, port = server.sockets[0].getsockname()[:2]

    try:
        methods = await Client(host, port).call("_synapse.methods")
        assert isinstance(methods, list)
        assert {method["name"] for method in methods} == {"public.tool"}
        assert methods[0]["description"] == "A public tool"
    finally:
        await agent.stop()
