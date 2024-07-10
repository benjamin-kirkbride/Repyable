import logging
import socket
import time

import pytest

from tests.util import Timer, UDPReceiver, get_udp_receivers
from tests.util.real_world_socket import get_real_world_sockets

logger = logging.getLogger(__name__)


def test_real_world_udp_socket_send_recv() -> None:
    # Create two sockets
    with get_real_world_sockets("client", "server") as rws_dict:
        server, client = rws_dict["server"], rws_dict["client"]

        # Bind server to a specific address
        server.bind(("localhost", 0))
        address = server.getsockname()

        # Send data from client to server
        test_data = b"Hello, World!"
        client.sendto(test_data, address)

        # Receive data on server
        received_data = server.recv(1024)

    # Check if the received data matches the sent data
    assert (
        received_data == test_data
    ), f"Expected {test_data!r}, but received {received_data!r}"


@pytest.mark.parametrize(
    ("num_packets", "test_data"),
    [
        (100, b"Hello, World!"),
        (1_000, b"Hello, World!"),
        (10_000, b"Hello, World!"),
        (10, b"Hello, World!" * 50),
        (100, b"Hello, World!" * 50),
        (1_000, b"Hello, World!" * 50),
    ],
)
def benchmark_bandwidth(num_packets: int, test_data: bytes) -> None:
    """Compare a real world socket with a normal socket in bandwidth."""
    # Create two normal sockets
    normal_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    with get_udp_receivers("normal_server") as rws_dict:
        normal_server = rws_dict["normal_server"]

        with Timer("normal socket sending timer") as normal_timer:
            for _ in range(num_packets):
                normal_socket.sendto(test_data, normal_server.bound_address)

    assert normal_server.exception is None
    assert len(normal_server.result) == num_packets

    with get_real_world_sockets("client") as rws_dict:
        # Create two real world sockets
        real_world_client = rws_dict["client"]

        receiver_server = UDPReceiver(bind_address=("localhost", 0))
        receiver_server.start()

        with Timer("sending timer") as real_world_timer:
            for _ in range(num_packets):
                real_world_client.sendto(test_data, receiver_server.bound_address)
        # queueing up packets using the real world socket is faster
        # UNLESS there are extremely few packets, but we can ignore that case
        assert (
            normal_timer.total_time > real_world_timer.total_time
            or real_world_timer.total_time < 0.005  # noqa: PLR2004
        )

        # Wait for the real world server to receive all packets
        while not real_world_client.empty:
            time.sleep(0.001)
