import enum
import struct
from typing import NamedTuple
from zlib import adler32

# Header format:
# !: network byte order
# B: 1 byte for the protocol version
# H: 2 bytes for packet type
# Q: 8 bytes for adler32 checksum of the payload

_header_format = "!BHQ"

_header_struct = struct.Struct(_header_format)


class RejectReasons(enum.StrEnum):
    """Connection reject reasons."""

    # Common
    WRONG_PROTOCOL_VERSION = enum.auto()
    NOT_CONNECTED = enum.auto()

    # Connect
    SERVER_FULL = enum.auto()


class PacketType(enum.IntEnum):
    """Packet type."""

    # Common
    KEEP_ALIVE = enum.auto()

    # Server
    ACCEPT = enum.auto()
    REJECT = enum.auto()

    # Client
    REQUEST_CONNECT = enum.auto()
    REQUEST_DISCONNECT = enum.auto()


class ChecksumMismatchError(Exception):
    """Checksum mismatch error."""

    def __init__(self, message: str = "Checksum mismatch") -> None:
        """Init."""
        super().__init__(message)


class Header(NamedTuple):
    """Header."""

    packet_type: int
    checksum: int

    def pack(self) -> bytes:
        """Pack."""
        return _header_struct.pack(self.packet_type, self.checksum)

    @classmethod
    def unpack(cls, data: bytes) -> "Header":
        """Unpack."""
        packet_type, checksum = _header_struct.unpack(data)
        return cls(packet_type, checksum)


class Payload(bytes):
    """Payload."""

    def __new__(cls, data: bytes) -> "Payload":
        """New."""
        return super().__new__(cls, data)

    def __init__(self, data: bytes):
        """Init."""
        self.checksum = adler32(data)

    def __repr__(self) -> str:
        """Repr."""
        return f"Payload({super().__repr__()})"


class Packet(NamedTuple):
    """Packet."""

    header: Header
    payload: Payload

    def pack(self) -> bytes:
        """Pack."""
        return self.header.pack() + self.payload

    @classmethod
    def unpack(cls, data: bytes) -> "Packet":
        """Unpack."""
        header = Header.unpack(data[: _header_struct.size])
        payload = Payload(data[_header_struct.size :])

        if payload.checksum != header.checksum:
            raise ChecksumMismatchError

        return cls(header, payload)
