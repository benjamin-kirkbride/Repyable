"""Tests for the RealWorldUDPSocket class."""

from tests.util.real_world_socket import RealWorldUDPSocket


def test_real_world_udp_socket_send_recv() -> None:
    # Create two sockets
    socket1 = RealWorldUDPSocket()
    socket2 = RealWorldUDPSocket()

    # Bind socket2 to a specific address
    socket2.bind(("localhost", 0))
    address = socket2.getsockname()

    # Start the sockets
    socket1.start()
    socket2.start()

    try:
        # Send data from socket1 to socket2
        test_data = b"Hello, World!"
        socket1.sendto(test_data, address)

        # Receive data on socket2
        received_data = socket2.recv(1024)

        # Check if the received data matches the sent data
        assert received_data == test_data, f"Expected {test_data!r}, but received {received_data!r}"

    finally:
        # Stop and close the sockets
        socket1.stop()
        socket2.stop()
        socket1.close()
        socket2.close()

def test_packet_loss() -> None:
    socket1 = RealWorldUDPSocket()
    socket2 = RealWorldUDPSocket()

    socket2._socket.bind(("localhost", 0))
    address = socket2._socket.getsockname()

    socket1.start()
    socket2.start()

    try:
        # Set a high packet loss rate
        socket1.packet_loss_rate = 1.0

        # Send multiple packets
        test_data = b"Test Packet"
        num_packets = 10
        for _ in range(num_packets):
            socket1.sendto(test_data, address)

        # Try to receive packets
        received_packets = 0
        for _ in range(num_packets):
            try:
                socket2.recv(1024)
                received_packets += 1
            except TimeoutError:
                pass

        # Assert that no packets were received due to 100% packet loss
        assert received_packets == 0, f"Expected 0 packets, but received {received_packets}"

    finally:
        socket1.stop()
        socket2.stop()
        socket1.close()
        socket2.close()
