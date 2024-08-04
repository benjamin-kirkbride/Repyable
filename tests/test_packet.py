from hypothesis import example, given
from hypothesis import strategies as st

from repyable import packet


@given(payload=st.binary(), packet_type=st.sampled_from(packet.Type))
@example(payload=b"")
def test_packet_round_trip(payload: bytes, packet_type: packet.Type) -> None:
    """Test packet round trip."""
    packet_ = packet.Packet.create(packet_type, payload)
    packed = packet_.pack()
    unpacked = packet.Packet.from_bits(packed)
    assert unpacked.header.packet_type == packet_type
    assert unpacked.payload.to_bytes() == payload
