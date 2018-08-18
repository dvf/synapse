import asyncio


def current_version():
    return "1.0"


class TCPConnection(asyncio.Protocol):
    """
    A new TCPConnection instance will be created for each connecting client
    """

    def __init__(self):
        print("Inside TCPConnection init")
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        peer_name = transport.get_extra_info('peername')

        print(f'Connection from {peer_name}')

    def data_received(self, data):
        message = data.decode()

        print(f'Data received: {message!r}')

        print(f'Send: {message!r}')
        self.transport.write(data)

        print('Close the client socket')
        self.transport.close()
