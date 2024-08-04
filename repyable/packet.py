import enum
import logging
from typing import NamedTuple
from zlib import crc32

import bitstring
from more_itertools import last

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

_protocol_name = "repyable"
_version = "0.0.1"  # FIXME: get this from pyproject.toml

# this is a magic value that appended the payload when calculating the checksum
# ensures that the checksum is different for different versions of the protocol
_magic_prefix = f"{_protocol_name} {_version} long r4nd0m pr3f1x!!".encode()

# this is a magic value that is appended to the end of the payload
# protects against packet truncation
_trailer = b"REPY"


class ChecksumMismatchError(Exception):
    """Checksum mismatch error."""

    def __init__(self, message: str = "Checksum mismatch") -> None:
        """Init."""
        super().__init__(message)


class SerializationCheckMismatchError(Exception):
    """Serialize check mismatch error."""

    def __init__(self, message: str = "Serialize check mismatch") -> None:
        """Init."""
        super().__init__(message)


class CRC32(int):
    """CRC32."""

    def __new__(cls, crc32: int) -> "CRC32":
        """New."""
        if not isinstance(crc32, int):
            msg = "CRC32 must be an integer"
            raise TypeError(msg)
        if crc32 < 0:
            msg = "CRC32 must be a positive integer"
            raise ValueError(msg)

        return super().__new__(cls, crc32)

    @classmethod
    def generate(cls, data: bytes) -> "CRC32":
        """Generate CRC32."""
        if not isinstance(data, bytes):
            msg = "Data must be bytes"
            raise TypeError(msg)

        return super().__new__(cls, crc32(data + _magic_prefix))

    def __repr__(self) -> str:
        """Repr."""
        return f"CRC32({super().__repr__()})"


_header_format = "uint:32, uint:2"
_header_bit_len = len(bitstring.pack(_header_format, 1, 1))


class Type(enum.IntEnum):
    """Packet type."""

    A = enum.auto()
    B = enum.auto()
    C = enum.auto()


class Header(NamedTuple):
    """Header."""

    checksum: CRC32
    packet_type: Type

    def to_bits(self) -> bitstring.Bits:
        """Pack."""
        return bitstring.pack(_header_format, self.checksum, self.packet_type)

    @classmethod
    def from_bits(cls, data: bitstring.Bits) -> tuple["Header", bitstring.Bits]:
        """Unpack header and return remaining data."""
        raw_header, remainder = data[:_header_bit_len], data[_header_bit_len:]
        checksum, packet_type = raw_header.unpack(_header_format)
        assert isinstance(checksum, int)
        assert not isinstance(checksum, bool)
        assert isinstance(packet_type, int)

        return cls(checksum=CRC32(checksum), packet_type=Type(packet_type)), remainder


_packet_overhead = _header_bit_len + (len(_trailer) * 8)


class Payload(bitstring.Bits):
    """Payload."""

    def __new__(cls, data: bytes) -> "Payload":
        """New."""
        print(f"Payload.__new__({data!r})")

        return super().__new__(cls, data)

    def __init__(self, data: bytes | bitstring.Bits):
        """Init."""
        if isinstance(data, bytes):
            self.checksum = CRC32.generate(data)
        else:
            self.checksum = CRC32.generate(data.tobytes())

        print(f"CRC32: {self.checksum}")

        super().__init__(data)

    def __repr__(self) -> str:
        """Repr."""
        return f"Payload({super().__repr__()})"

    def to_bytes(self) -> bytes:
        """To bytes."""
        return self.tobytes()


class Packet(NamedTuple):
    """Packet."""

    header: Header
    payload: Payload

    def pack(self) -> bitstring.Bits:
        """Pack."""
        header = self.header.to_bits()
        return header + self.payload + _trailer

    @classmethod
    def create(
        cls, packet_type: Type, payload: Payload | bytes | bitstring.Bits
    ) -> "Packet":
        """Create."""
        if isinstance(payload, Payload):
            header = Header(packet_type=packet_type, checksum=payload.checksum)
        elif isinstance(payload, bytes):
            payload = Payload(payload)
            header = Header(packet_type=packet_type, checksum=payload.checksum)
        else:
            assert isinstance(payload, bitstring.Bits)
            payload = Payload(payload)
            header = Header(packet_type=packet_type, checksum=payload.checksum)

        return cls(header, payload)

    @classmethod
    def from_bits(cls, data: bitstring.Bits) -> "Packet":
        """From bytes."""
        remainder = cls.strip_trailer(bitstring.Bits(data))

        header, payload = cls.unpack(remainder)
        assert isinstance(payload, Payload)

        return cls(header, payload)

    @classmethod
    def unpack(cls, data: bitstring.Bits) -> tuple[Header, Payload]:
        """Unpack the raw packet data into it's parts.

        Also validates.
        """
        header, remainder = Header.from_bits(data)
        payload = Payload(remainder)

        if not header.checksum == payload.checksum:
            raise ChecksumMismatchError

        return header, payload

    @classmethod
    def strip_trailer(cls, data: bitstring.Bits) -> bitstring.Bits:
        """Strip trailer."""
        _bit_trailer = bitstring.Bits(_trailer)
        # the trailer is always at the end of the packet
        # the conversion from bits to bytes can cause up to 7 bits of padding
        start_idx = len(data) - (len(_bit_trailer) + 7)

        trailer_index = last(data.findall(_bit_trailer, start=start_idx), None)

        if trailer_index is None:
            raise SerializationCheckMismatchError

        return data[:trailer_index]
