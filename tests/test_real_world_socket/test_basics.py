import logging
import statistics
import time

import pytest

from tests.util import Timer, UDPReceiverServer, get_udp_receivers, process_packets
from tests.util.real_world_socket import get_real_world_sockets
from tests.util.udp_receiver import ReceivedPacket

logger = logging.getLogger(__name__)


def test_real_world_udp_socket_send_recv() -> None:
    # Create two sockets
    with get_real_world_sockets("client", "server") as rws_dict:
        server, client = rws_dict["server"], rws_dict["client"]

        # Bind server to a specific address
        server.bind(("localhost", 0))
        address = server.getsockname()

        # Send data from client to server
        test_data = b"Hello, world!"
        client.sendto(test_data, address)

        # Receive data on server
        received_data = server.recv(1024)

    # Check if the received data matches the sent data
    assert (
        received_data == test_data
    ), f"Expected {test_data!r}, but received {received_data!r}"


@pytest.mark.parametrize(
    ("num_packets", "packet_size"),
    [
        # (25, None),
        # (256, None),
        # (2_560, None),
        (25_600, None),
        (25, 1200),
        (256, 1200),
        (2_560, 1200),
        (25_600, 1200),
    ],
)
def benchmark_real_world_socket_no_latency(
    num_packets: int, packet_size: int | None
) -> None:
    with (
        get_real_world_sockets("client") as rws_dict,
        get_udp_receivers("rw_receiver", children=10) as receiver_dict,
    ):
        real_world_client = rws_dict["client"]
        rw_receiver = receiver_dict["rw_receiver"]

        with Timer("real world socket sending timer") as real_world_timer:
            for i in range(num_packets):
                # if i % 100 == 0:
                #     time.sleep(0.01)
                data = f"[[{i}:{time.monotonic()}:]]"
                if packet_size is not None:
                    padding_len = packet_size - len(data)
                    data += "X" * padding_len
                real_world_client.sendto(data.encode(), rw_receiver.bound_address)

        real_world_client.ensure_empty_send_queue()

        time.sleep(2)

        rw_receiver.stop()
        time.sleep(2)

        rw_packets: list[ReceivedPacket] = []
        while not rw_receiver.receive_queue.empty():
            rw_packets.extend(rw_receiver.receive_queue.get())

        processed_rw_packets = process_packets(rw_packets)
        assert len(processed_rw_packets) == num_packets

    rw_latencies = [packet.latency() for packet in processed_rw_packets]

    # average rw latency should be less than 0.1ms
    assert (
        statistics.mean(rw_latencies) < 1 / 10_000
    ), f"Average latency >1ms: {statistics.mean(rw_latencies)*10000:.3f}ms"
