import asyncio

from electron.network import TCPConnection

LOCAL_ADDRESS = '127.0.0.1'
PORT = 8888

# Get or Create the Event Loop
loop = asyncio.get_event_loop()

# One protocol instance will be created to serve all client requests
coro = loop.create_server(TCPConnection, LOCAL_ADDRESS, PORT)
server = loop.run_until_complete(coro)

nodes = ['127.0.0.1']

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

# server.close()
# loop.run_until_complete(server.wait_closed())
loop.close()
