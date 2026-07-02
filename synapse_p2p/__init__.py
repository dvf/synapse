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
from synapse_p2p.conversations import (
    BaseConversationLog,
    MemoryConversationLog,
    SqliteConversationLog,
    default_summarizer,
)
from synapse_p2p.messages import RemoteProcedureCall, RPCError, RPCRequest, RPCResponse
from synapse_p2p.node import Capability, Node
from synapse_p2p.schedules import CronSchedule, IntervalSchedule, SolarSchedule, cron, every, solar
from synapse_p2p.serializers import BaseRPCSerializer, MessagePackRPCSerializer
from synapse_p2p.types import (
    AdvertisedArtifact,
    Broadcast,
    BroadcastReply,
    Connection,
    ConversationEvent,
    NodeKind,
    Peer,
    ServedArtifact,
)

logger.disable("synapse_p2p")

__all__ = [
    "AdvertisedArtifact",
    "Capability",
    "BaseConversationLog",
    "BaseRPCSerializer",
    "Broadcast",
    "BroadcastReply",
    "Client",
    "Connection",
    "ConversationEvent",
    "CronSchedule",
    "MemoryConversationLog",
    "MessagePackRPCSerializer",
    "Node",
    "NodeKind",
    "Peer",
    "RPCError",
    "RPCRequest",
    "RPCResponse",
    "RemoteProcedureCall",
    "ServedArtifact",
    "SqliteConversationLog",
    "IntervalSchedule",
    "SolarSchedule",
    "cron",
    "default_summarizer",
    "every",
    "solar",
    "__logo__",
    "__version__",
]
