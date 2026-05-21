from importlib.metadata import PackageNotFoundError, version

from loguru import logger

try:
    __version__ = version("synapse-p2p")
except PackageNotFoundError:
    __version__ = "0.0.0"

__logo__ = f"""
\033[32m
███████╗██╗   ██╗███╗   ██╗ █████╗ ██████╗ ███████╗███████╗
██╔════╝╚██╗ ██╔╝████╗  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝
███████╗ ╚████╔╝ ██╔██╗ ██║███████║██████╔╝███████╗█████╗
╚════██║  ╚██╔╝  ██║╚██╗██║██╔══██║██╔═══╝ ╚════██║██╔══╝
███████║   ██║   ██║ ╚████║██║  ██║██║     ███████║███████╗
╚══════╝   ╚═╝   ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝
\033[0m
\033[33m⚡ \033[35msynapse \033[36m{__version__}\033[0m
"""

from synapse_p2p.client import Client
from synapse_p2p.messages import RemoteProcedureCall, RPCError, RPCRequest, RPCResponse
from synapse_p2p.node import Capability, Node
from synapse_p2p.serializers import BaseRPCSerializer, MessagePackRPCSerializer
from synapse_p2p.types import Broadcast, BroadcastReply, Connection, NodeKind, Peer

logger.disable("synapse_p2p")

__all__ = [
    "Capability",
    "BaseRPCSerializer",
    "Broadcast",
    "BroadcastReply",
    "Client",
    "Connection",
    "MessagePackRPCSerializer",
    "Node",
    "NodeKind",
    "Peer",
    "RPCError",
    "RPCRequest",
    "RPCResponse",
    "RemoteProcedureCall",
    "__logo__",
    "__version__",
]
