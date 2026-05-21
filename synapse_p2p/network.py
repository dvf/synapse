import socket


def host_id() -> str:
    """Stable-enough local host identifier for same-machine peer detection."""
    return socket.gethostname()


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


def is_local_address(address: str) -> bool:
    if address.startswith("127.") or address in {"localhost", "::1"}:
        return True
    return address == local_ip()


def connect_address(address: str) -> str:
    """Prefer loopback when connecting to this same machine."""
    return "127.0.0.1" if is_local_address(address) else address


def advertised_address(bind: str, advertise: str | None) -> str:
    if advertise and advertise != "auto":
        return advertise
    if bind in {"0.0.0.0", "::", ""}:
        return local_ip()
    return bind
