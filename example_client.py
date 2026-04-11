import socket

from synapse_p2p import RemoteProcedureCall
from synapse_p2p.serializers import MessagePackRPCSerializer


def main() -> None:
    with socket.create_connection(("127.0.0.1", 9999)) as sock:
        sock.sendall(
            MessagePackRPCSerializer.serialize(RemoteProcedureCall(endpoint="sum", args=[1, 2]))
        )
        data = sock.recv(1024)

    print(f"Received:\n{data.decode()}")


if __name__ == "__main__":
    main()
