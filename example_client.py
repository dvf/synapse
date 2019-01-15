import socket

from electron.messages import RemoteProcedureCall

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

sock.connect(("127.0.0.1", 9999))
sock.send(RemoteProcedureCall(endpoint="sum", args=[1, 2]).encode())

data = sock.recv(1024)
print(f"Received: \n{data.decode()}")
sock.close()
