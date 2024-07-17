"""Tests for jitter in the RealWorldUDPSocket class."""

import pytest

from tests.util.real_world_socket import get_real_world_sockets


@pytest.mark.parametrize("num_packets", [500, 5000, 50000])
@pytest.mark.parametrize("base_latency", [0, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5])
@pytest.mark.parametrize("jitter", [0, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5])
def test_jitter(num_packets: int, base_latency: float, jitter: float) -> None:
    with (get_real_world_sockets("client") as rws_dict,):
        client = rws_dict["client"]
        client.base_latency = base_latency
        client.jitter = jitter

        latencies = [client._simulate_latency() for _ in range(num_packets)]

    min_latency = min(latencies)
    min_accepted_latency = base_latency - 0.0015
    max_latency = max(latencies)
    max_accepted_latency = base_latency + jitter + 0.005

    assert (
        min_latency >= min_accepted_latency
    ), f"min_latency: {min_latency*1000}ms <= {min_accepted_latency*1000}ms"
    assert (
        max_latency <= max_accepted_latency
    ), f"max_latency: {max_latency*1000}ms >= {max_accepted_latency*1000}ms"
