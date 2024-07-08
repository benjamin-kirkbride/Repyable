import logging
import multiprocessing
import socket
import time
from functools import partial
from typing import Any, Callable

from tests.util.real_world_socket import RealWorldUDPSocket

logger = logging.getLogger(__name__)


def test_real_world_udp_socket_send_recv() -> None:
    # Create two sockets
    client = RealWorldUDPSocket(name="client")
    server = RealWorldUDPSocket(name="server")
    server.settimeout(1)

    # Bind server to a specific address
    server.bind(("localhost", 0))
    address = server.getsockname()

    # Start the sockets
    client.start_scheduler()
    server.start_scheduler()

    try:
        # Send data from client to server
        test_data = b"Hello, World!"
        client.sendto(test_data, address)

        # Receive data on server
        received_data = server.recv(1024)

        # Check if the received data matches the sent data
        assert (
            received_data == test_data
        ), f"Expected {test_data!r}, but received {received_data!r}"

    finally:
        # Stop and close the sockets
        client.stop_scheduler()
        server.stop_scheduler()
        client.close()
        server.close()


class ExecuteXTimes(multiprocessing.Process):
    """Execute a function `num_times` times in a separate process."""

    def __init__(self, func: Callable[..., Any], num_times: int):
        """Initializes an ExecuteXTimes object."""
        super().__init__()
        self.func = func
        self.num_times = num_times

    def run(self):
        """Run the function `num_times` times."""
        try:
            for _ in range(self.num_times):
                self.func()
        except Exception as e:
            logger.critical(f"An error occurred: {e}")
            raise
        finally:
            logger.debug("Process completed")


def benchmark_bandwidth():
    """Compare a real world socket with a normal socket in bandwidth."""
    max_time_diff = 0
    total_packets = 10
    test_data = b"Hello, World!"

    # Create two normal sockets
    normal_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    normal_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    normal_server.settimeout(1)

    # Bind server to a specific address
    normal_server.bind(("localhost", 0))
    normal_address = normal_server.getsockname()

    # Time the normal socket
    normal_start_time = time.time()

    normal_client_process = ExecuteXTimes(
        func=partial(normal_client.sendto, test_data, normal_address),
        num_times=total_packets,
    )
    normal_server_process = ExecuteXTimes(
        func=partial(normal_server.recv, 1024),
        num_times=total_packets,
    )
    normal_client_process.start()
    normal_server_process.start()
    normal_client_process.join()
    normal_server_process.join()

    normal_time = time.time() - normal_start_time

    # Create two real world sockets
    real_world_client = RealWorldUDPSocket(name="client")
    real_world_server = RealWorldUDPSocket(name="server")

    # Bind server to a specific address
    real_world_server.bind(("localhost", 0))
    real_world_address = real_world_server.getsockname()

    # Start the sockets
    real_world_client.start_scheduler()
    real_world_server.start_scheduler()

    try:
        # Time the real world socket
        real_world_start_time = time.time()

        real_world_client_receiver_process = ExecuteXTimes(
            func=partial(real_world_client.sendto, test_data, real_world_address),
            num_times=total_packets,
        )
        real_world_server_receiver_process = ExecuteXTimes(
            func=partial(real_world_server.recv, 1024),
            num_times=total_packets,
        )
        real_world_server_receiver_process.start()
        time.sleep(0.1)
        real_world_client_receiver_process.start()
        real_world_client_receiver_process.join(timeout=10)
        real_world_server_receiver_process.join(timeout=10)
        assert not real_world_client_receiver_process.is_alive()
        assert not real_world_server_receiver_process.is_alive()

        real_world_time = time.time() - real_world_start_time

    finally:
        # Stop and close the sockets

        if real_world_client.scheduler_is_alive():
            real_world_client.stop_scheduler()
        if real_world_server.scheduler_is_alive():
            real_world_server.stop_scheduler()

        real_world_client.join_scheduler(timeout=1)
        assert not real_world_client.scheduler_is_alive()
        real_world_server.join_scheduler(timeout=1)
        assert not real_world_server.scheduler_is_alive()

    # Real world socket must be within `max_time_diff` percentage of normal socket
    assert real_world_time < normal_time * (1 + max_time_diff), (
        f"Real world socket took {real_world_time:.3f} seconds"
        f", while normal socket took {normal_time:.3f} seconds"
    )
