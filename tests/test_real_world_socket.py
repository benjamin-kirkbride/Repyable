"""Tests for the RealWorldUDPSocket class."""

import time

from tests.util.real_world_socket import RealWorldUDPSocket

# Constants
TIMEOUT_SECONDS = 5
LOWER_LOSS_RATE = 0.45
UPPER_LOSS_RATE = 0.55


def test_real_world_udp_socket_send_recv() -> None:
    # Create two sockets
    client = RealWorldUDPSocket(name="client")
    server = RealWorldUDPSocket(name="server")
    server.settimeout(1)

    # Bind socket2 to a specific address
    server.bind(("localhost", 0))
    address = server.getsockname()

    # Start the sockets
    client.start()
    server.start()

    try:
        # Send data from socket1 to socket2
        test_data = b"Hello, World!"
        client.sendto(test_data, address)

        # Receive data on socket2
        received_data = server.recv(1024)

        # Check if the received data matches the sent data
        assert (
            received_data == test_data
        ), f"Expected {test_data!r}, but received {received_data!r}"

    finally:
        # Stop and close the sockets
        client.stop()
        server.stop()
        client.close()
        server.close()


def test_fifty_percent_packet_loss() -> None:
    client = RealWorldUDPSocket(name="client")
    server = RealWorldUDPSocket(name="server")
    server.settimeout(0.1)

    server.bind(("localhost", 0))
    address = server.getsockname()

    client.start()
    server.start()

    try:
        # Set 50% packet loss rate
        client.packet_loss_rate = 0.5

        # Send 1000 packets
        test_data = b"Test Packet"
        num_packets = 1000
        for _ in range(num_packets):
            client.sendto(test_data, address)

        # Try to receive packets
        received_packets = 0
        start_time = time.time()
        while time.time() - start_time < TIMEOUT_SECONDS:
            try:
                server.recv(1024)
                received_packets += 1
            except TimeoutError:
                continue

        # Calculate the actual loss rate
        loss_rate = (num_packets - received_packets) / num_packets

        # Assert that the loss rate is within 5% of 50%
        assert (
            LOWER_LOSS_RATE <= loss_rate <= UPPER_LOSS_RATE
        ), f"Expected loss rate between {LOWER_LOSS_RATE * 100}% and {UPPER_LOSS_RATE * 100}%, but got {loss_rate * 100:.2f}%"

    finally:
        client.stop()
        server.stop()
        client.close()
        server.close()


def test_total_packet_loss() -> None:
    client = RealWorldUDPSocket(name="client")
    server = RealWorldUDPSocket(name="server")
    server.settimeout(0.1)

    server.bind(("localhost", 0))
    address = server.getsockname()

    client.start()
    server.start()

    try:
        # Set a high packet loss rate
        client.packet_loss_rate = 1.0

        # Send multiple packets
        test_data = b"Test Packet"
        num_packets = 10
        for _ in range(num_packets):
            client.sendto(test_data, address)

        # Try to receive packets
        received_packets = 0
        for _ in range(num_packets):
            try:
                server.recv(1024)
                received_packets += 1
            except TimeoutError:
                break

        # Assert that no packets were received due to 100% packet loss
        assert (
            received_packets == 0
        ), f"Expected 0 packets, but received {received_packets}"

    finally:
        client.stop()
        server.stop()
        client.close()
        server.close()
