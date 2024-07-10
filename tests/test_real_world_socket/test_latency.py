"""Tests for jitter in the RealWorldUDPSocket class."""

import math
import time
from statistics import mean, stdev

import pytest

from tests.util.real_world_socket import (
    PacketWithTime,
    ReceiveProcess,
    get_real_world_sockets,
)


# TODO: testing latency does not require serial execution of packet sending
# this could be much faster if we send all packets at once and then receive them
@pytest.mark.parametrize(
    ("num_packets", "base_latency", "jitter"),
    [
        (1000, 0.050, 0.010),
        (200, 0.100, 0.150),
        (100, 0.200, 0.300),
        (50, 0.500, 0.250),
    ],
)
def test_jitter(num_packets: int, base_latency: float, jitter: float) -> None:
    with get_real_world_sockets("client", "server") as rws_dict:
        # give 50ms of extra time for the packets to be processed
        safe_max_latency = (base_latency + jitter) + 0.050

        client, server = rws_dict["client"], rws_dict["server"]
        server.settimeout(1)

        server.bind(("localhost", 0))
        address = server.getsockname()

        # Set the base latency and jitter range
        client.base_latency = base_latency
        client.jitter = jitter

        server_receiver_process = ReceiveProcess(sock=server, timeout=safe_max_latency)
        server_receiver_process.start()
        # time.sleep(0.1)  # let the server start

        for i in range(num_packets):
            data = f"[[{i}:{time.monotonic()}:Hello World!]]".encode()
            client.sendto(data, address)

        # give time for client to send scheduled packets
        time.sleep(safe_max_latency + 0.1)
        if server_receiver_process.is_alive():
            server_receiver_process.stop()
        # time for the server to timeout on socket.recv
        server_receiver_process.join(timeout=safe_max_latency)
        assert not server_receiver_process.is_alive()
        packets: list[PacketWithTime] = server_receiver_process.result

        packet_numbers = {packet.number for packet in packets}
        assert len(packet_numbers) == num_packets

        for packet in packets:
            # this is generous but still useful
            assert packet.latency() < safe_max_latency

        # Calculate statistics
        latencies = [packet.latency() for packet in packets]

        # Check if the average latency is within the expected range
        avg_tolerance = 5 / 100
        avg_latency = mean(latencies)
        expected_avg = (jitter / 2) + base_latency
        assert math.isclose(avg_latency, expected_avg, rel_tol=avg_tolerance)

        # Check if the standard deviation is reasonable
        stdev_tolerance = 10 / 100
        latency_stdev = stdev(latencies)
        expected_stdev = jitter * (1 / math.sqrt(12))
        assert math.isclose(latency_stdev, expected_stdev, rel_tol=stdev_tolerance)
