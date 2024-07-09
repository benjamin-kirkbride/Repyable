import logging
import math
import socket
import time
from functools import partial

import pytest

from repyable.safe_process import SafeProcess
from tests.util import repeat_callable
from tests.util.real_world_socket import get_multiple_real_world_sockets

logger = logging.getLogger(__name__)


def test_real_world_udp_socket_send_recv() -> None:
    # Create two sockets
    with get_multiple_real_world_sockets("client", "server") as rws_dict:
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
    normal_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    normal_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    normal_server.settimeout(1)

    # Bind server to a specific address
    normal_server.bind(("localhost", 0))
    normal_address = normal_server.getsockname()

    # Time the normal socket
    normal_start_time = time.time()

    normal_client_process = SafeProcess(
        target=repeat_callable(
            func=partial(normal_client.sendto, test_data, normal_address),
            num_times=num_packets,
        )
    )

    normal_server_process = SafeProcess(
        target=repeat_callable(
            func=partial(normal_server.recv, 1024),
            num_times=num_packets,
        )
    )

    normal_client_process.start()
    normal_server_process.start()
    normal_client_process.join()
    normal_server_process.join()
    assert not normal_client_process.is_alive()
    assert not normal_server_process.is_alive()
    assert normal_client_process.exception is None
    assert normal_server_process.exception is None

    normal_time = time.time() - normal_start_time

    with get_multiple_real_world_sockets("client", "server") as rws_dict:
        # Create two real world sockets
        real_world_client, real_world_server = rws_dict["client"], rws_dict["server"]

        # Bind server to a specific address
        real_world_server.bind(("localhost", 0))
        real_world_address = real_world_server.getsockname()

        # Time the real world socket
        real_world_start_time = time.time()

        real_world_client_sender_process = SafeProcess(
            target=repeat_callable(
                func=partial(real_world_client.sendto, test_data, real_world_address),
                num_times=num_packets,
            )
        )
        real_world_server_receiver_process = SafeProcess(
            target=repeat_callable(
                func=partial(real_world_server.recv, 1024),
                num_times=num_packets,
            )
        )

        real_world_server_receiver_process.start()
        real_world_client_sender_process.start()

        real_world_client_sender_process.join(timeout=10)
        real_world_server_receiver_process.join(timeout=10)
        assert real_world_client_sender_process.exception is None
        assert real_world_server_receiver_process.exception is None
        assert not real_world_client_sender_process.is_alive()
        assert not real_world_server_receiver_process.is_alive()

        real_world_time = time.time() - real_world_start_time

    tolerance = 50 / 100
    assert math.isclose(real_world_time, normal_time, rel_tol=tolerance), (
        f"Real world socket took {real_world_time:.3f} seconds"
        f", while normal socket took {normal_time:.3f} seconds"
    )
