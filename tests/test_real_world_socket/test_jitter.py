"""Tests for jitter in the RealWorldUDPSocket class."""

import time
from statistics import mean, stdev

import pytest

from tests.util.real_world_socket import RealWorldUDPSocket


@pytest.mark.parametrize(
    "base_latency, jitter_range",
    [
        (0.1, (0.05, 0.15)),
        (0.2, (0.1, 0.3)),
    ],
)
def test_jitter(base_latency: float, jitter_range: tuple[float, float]) -> None:
    client = RealWorldUDPSocket(name="client")
    server = RealWorldUDPSocket(name="server")
    server.settimeout(1)

    server.bind(("localhost", 0))
    address = server.getsockname()

    client.start()
    server.start()

    # Set the base latency and jitter range
    client.base_latency = base_latency
    client.jitter_range = jitter_range

    try:
        # Send multiple packets and measure the time it takes for each
        test_data = b"Test Packet"
        num_packets = 100
        latencies = []

        for _ in range(num_packets):
            start_time = time.time()
            client.sendto(test_data, address)
            server.recv(1024)
            end_time = time.time()
            latencies.append(end_time - start_time)

        # Calculate statistics
        avg_latency = mean(latencies)
        latency_stdev = stdev(latencies)

        # Check if the average latency is within the expected range
        expected_avg = base_latency + (jitter_range[0] + jitter_range[1]) / 2
        assert abs(avg_latency - expected_avg) < 0.05, (
            f"Expected average latency around {expected_avg:.3f}, "
            f"but got {avg_latency:.3f}"
        )

        # Check if the standard deviation is reasonable
        expected_stdev = (jitter_range[1] - jitter_range[0]) / 4  # Approximate
        assert abs(latency_stdev - expected_stdev) < 0.05, (
            f"Expected latency standard deviation around {expected_stdev:.3f}, "
            f"but got {latency_stdev:.3f}"
        )

    finally:
        client.stop()
        server.stop()
        client.close()
        server.close()
