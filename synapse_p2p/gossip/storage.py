import asyncio

import aiosqlite


class PeerStorage:
    DATABASE = "db.sqlite3"

    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.build_peer_table())

    async def build_peer_table(self):
        async with aiosqlite.connect(self.DATABASE) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS peers (ip text, port number);")
            await db.commit()

    async def add_peer(self, ip, port):
        async with aiosqlite.connect(self.DATABASE) as db:
            await db.execute("INSERT INTO peers (ip, port) VALUES (?, ?)", (ip, port))
            await db.commit()
