import socket

LOCAL_IP = "0.0.0.0"
LOCAL_PORT = 9999

REMOTE_IP = "seed.dvf.nyc"
REMOTE_PORT = 9999

if __name__ == "__main__":
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LOCAL_IP, LOCAL_PORT))

    #sock.sendto("hi".encode(), (REMOTE_IP, REMOTE_PORT))
    data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
    print(data, addr)
