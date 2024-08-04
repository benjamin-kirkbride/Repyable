"""Init."""

import enum
from typing import NamedTuple

MAX_PACKET_SIZE = 1200
MAX_CLIENTS: int = 64
TIMEOUT: float = 5.0
PACKET_SALT_SIZE: int = 8


class ClientStatus(enum.StrEnum):
    """Client status."""

    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"


class Address(NamedTuple):
    """Address."""

    address: str
    port: int
