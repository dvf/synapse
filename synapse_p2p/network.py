import socket


def local_ip() -> str:
    """Best-effort LAN-reachable IPv4 address for advertising to peers."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
    except OSError:
        address = socket.gethostbyname(socket.gethostname())
    finally:
        sock.close()

    if address.startswith("127."):
        return "127.0.0.1"
    return address


def advertised_address(bind: str, advertise: str | None) -> str:
    if advertise and advertise != "auto":
        return advertise
    if bind in {"0.0.0.0", "::", ""}:
        return local_ip()
    return bind
