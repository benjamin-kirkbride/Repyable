import logging
import math
import socket
import statistics
import time

import pytest

from tests.util import Timer, UDPReceiverServer, get_udp_receivers, process_packets
from tests.util.real_world_socket import get_real_world_sockets


def benchmark_bandwidth(num_packets: int, padding: str) -> None:
    """Compare a real world socket with a normal socket in bandwidth."""
    with (
        get_real_world_sockets("client") as rws_dict,
        get_udp_receivers("real_world_server") as receiver_dict,
    ):
        real_world_client = rws_dict["client"]
        receiver = receiver_dict["real_world_server"]

        with Timer("real world socket sending timer") as real_world_timer:
            for i in range(num_packets):
                data = f"[[{i}:{time.monotonic()}:{padding}]]".encode()
                real_world_client.sendto(data, receiver.bound_address)

        real_world_client.ensure_empty_send_queue()

        receiver.stop()
        assert receiver.exception is None
        rw_packets = list(receiver.result_queue.get())
        processed_rw_packets = process_packets(rw_packets)
        assert (
            len(processed_rw_packets) == num_packets
        ), f"len(processed_rw_packets)={len(processed_rw_packets)} != num_packets={num_packets}"

    rw_latencies = [packet.latency() for packet in processed_rw_packets]

    # average rw latency should be less than 1ms
    assert (
        statistics.mean(rw_latencies) < 1 / 1_000
    ), f"Average latency >1ms: {statistics.mean(rw_latencies)*1000:.3f}ms"

    print("DONE")


if __name__ == "__main__":
    benchmark_bandwidth(256, "Hello, World!" * 50)
