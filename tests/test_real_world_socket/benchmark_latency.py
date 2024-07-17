import math
import statistics
import time
from typing import TYPE_CHECKING

import pytest

from tests.util import (
    MAX_PACKET_PER_SECOND,
    Timer,
    get_udp_receivers,
    process_packets,
)
from tests.util.real_world_socket import get_real_world_sockets

if TYPE_CHECKING:
    from tests.util.udp_receiver import ReceivedPacket


@pytest.mark.parametrize("packet_size", [None, 1200])
@pytest.mark.parametrize("base_latency", [0, 0.001, 0.005, 0.01, 0.05, 0.1, 1])
@pytest.mark.parametrize("num_packets", [25, 256, 2_560, 25_600])
def benchmark_real_world_socket_with_constant_latency(
    num_packets: int, packet_size: int | None, base_latency: float
) -> None:
    with (
        get_real_world_sockets("client") as rws_dict,
        get_udp_receivers("rw_receiver", children=3) as receiver_dict,
    ):
        real_world_client = rws_dict["client"]
        real_world_client.base_latency = base_latency
        rw_receiver = receiver_dict["rw_receiver"]

        with Timer("real world socket sending timer"):
            for i in range(num_packets):
                data = f"[[{i}:{time.monotonic() + (1/MAX_PACKET_PER_SECOND)*i}:]]"

                if packet_size is not None:
                    padding_len = packet_size - len(data)
                    data += "X" * padding_len

                real_world_client.sendto(
                    data.encode(),
                    rw_receiver.bound_address,
                    delay=(1 / MAX_PACKET_PER_SECOND) * i,
                )

        real_world_client.ensure_empty_send_queue()

        time.sleep(0.05 + (1 / MAX_PACKET_PER_SECOND) * num_packets)
        rw_receiver.stop()
        time.sleep(0.05 + (1 / MAX_PACKET_PER_SECOND) * num_packets)

        rw_packets: list[ReceivedPacket] = []
        while not rw_receiver.receive_queue.empty():
            rw_packets.extend(rw_receiver.receive_queue.get())

        processed_rw_packets = process_packets(rw_packets)
        assert len(processed_rw_packets) == num_packets

    latencies = [packet.latency() for packet in processed_rw_packets]

    min_latency = min(latencies)
    max_latency = max(latencies)
    print(
        f"Min latency: {min_latency*1000:.3f}ms, Max latency: {max_latency*1000:.3f}ms"
    )

    # average rw latency should be less than 0.1ms
    assert math.isclose(
        statistics.mean(latencies), base_latency, rel_tol=0.1, abs_tol=0.001
    ), f"Average latency >{base_latency*1000}ms: {statistics.mean(latencies)*1000:.3f}ms"
