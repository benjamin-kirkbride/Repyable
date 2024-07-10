"""Tests for the RealWorldUDPSocket class."""

import pytest

from tests.util.real_world_socket import RealWorldUDPSocket


@pytest.mark.parametrize("expected_loss_rate", [i / 100 for i in range(5, 100, 5)])
def test_packet_loss(expected_loss_rate: float) -> None:
    # Constants
    tolerance = 0.05  # 5% tolerance
    lower_loss_rate = max(0, expected_loss_rate - tolerance)
    upper_loss_rate = min(1, expected_loss_rate + tolerance)

    client = RealWorldUDPSocket(name="client")
    server = RealWorldUDPSocket(name="server")
    server.settimeout(0.1)

    server.bind(("localhost", 0))
    address = server.getsockname()

    client.start_sender()
    server.start_sender()

    # Set the packet loss rate
    client.packet_loss_rate = expected_loss_rate

    try:
        # Send 1000 packets
        test_data = b"Test Packet"
        num_packets = 1000
        for _ in range(num_packets):
            client.sendto(test_data, address)

        # Try to receive packets
        received_packets = 0
        while True:
            try:
                server.recv(1024)
                received_packets += 1
            except TimeoutError:
                break

        # Calculate the actual loss rate
        actual_loss_rate = (num_packets - received_packets) / num_packets

        # Assert that the loss rate is within the tolerance range
        assert (
            lower_loss_rate <= actual_loss_rate <= upper_loss_rate
        ), f"Expected loss rate between {lower_loss_rate:.2f} and {upper_loss_rate:.2f}, but got {actual_loss_rate:.2f}"

    finally:
        client.stop_sender()
        server.stop_sender()
        client.close()
        server.close()


def test_total_packet_loss() -> None:
    client = RealWorldUDPSocket(name="client")
    server = RealWorldUDPSocket(name="server")
    server.settimeout(0.1)

    server.bind(("localhost", 0))
    address = server.getsockname()

    client.start_sender()
    server.start_sender()

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
        client.stop_sender()
        server.stop_sender()
        client.close()
        server.close()
