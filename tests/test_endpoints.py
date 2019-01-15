import pytest

from electron.types import Node


class TestIntro:
    @pytest.mark.asyncio
    async def test_intro_happy_path(self, server, intro, node):
        await server.intro(message=intro, caller=Node(**node))
        assert len(server.neighborhood) == len(intro.nodes) + 1
