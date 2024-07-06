import socket
import struct
import threading
import time
from typing import Callable, List, NamedTuple, Optional, Tuple


class Packet(NamedTuple):
    sequence: int
    data: bytes


class ReliableEndpoint:
    def __init__(
        self,
        sock: socket.socket,
        max_packet_size: int = 1200,
        fragment_above: int = 1000,
        max_fragments: int = 16,
        fragment_size: int = 500,
        ack_buffer_size: int = 32,
        sent_packets_buffer_size: int = 256,
        received_packets_buffer_size: int = 256,
        rtt_smoothing_factor: float = 0.1,
        packet_loss_smoothing_factor: float = 0.1,
        bandwidth_smoothing_factor: float = 0.1,
        process_packet_callback: Callable[[bytes], bool] = lambda x: True,
    ):
        self.sock = sock
        self.max_packet_size = max_packet_size
        self.fragment_above = fragment_above
        self.max_fragments = max_fragments
        self.fragment_size = fragment_size
        self.ack_buffer_size = ack_buffer_size
        self.sent_packets_buffer_size = sent_packets_buffer_size
        self.received_packets_buffer_size = received_packets_buffer_size
        self.rtt_smoothing_factor = rtt_smoothing_factor
        self.packet_loss_smoothing_factor = packet_loss_smoothing_factor
        self.bandwidth_smoothing_factor = bandwidth_smoothing_factor
        self.process_packet_callback = process_packet_callback

        self.sequence = 0
        self.acks: List[int] = []
        self.sent_packets: List[Optional[Packet]] = [None] * sent_packets_buffer_size
        self.received_packets: List[Optional[Packet]] = [
            None
        ] * received_packets_buffer_size
        self.fragments: dict = {}

        self.rtt = 0.0
        self.packet_loss = 0.0
        self.sent_bandwidth = 0.0
        self.received_bandwidth = 0.0
        self.acked_bandwidth = 0.0

        self.last_update_time = time.time()
        self.running = False
        self.receive_thread = None

    def start(self) -> None:
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.start()

    def stop(self) -> None:
        self.running = False
        if self.receive_thread:
            self.receive_thread.join()

    def _receive_loop(self) -> None:
        while self.running:
            try:
                data, addr = self.sock.recvfrom(self.max_packet_size)
                self._process_received_data(data)
            except socket.timeout:
                pass

    def _process_received_data(self, data: bytes) -> None:
        sequence, ack, ack_bits = struct.unpack("!HHI", data[:8])
        payload = data[8:]

        if len(payload) > self.fragment_above:
            self._process_fragment(sequence, payload)
        else:
            self._process_packet(sequence, payload)

        self._process_acks(ack, ack_bits)

    def _process_fragment(self, sequence: int, data: bytes) -> None:
        fragment_id, total_fragments = struct.unpack("!BB", data[:2])
        fragment_data = data[2:]

        if sequence not in self.fragments:
            self.fragments[sequence] = [None] * total_fragments

        self.fragments[sequence][fragment_id] = fragment_data

        if all(self.fragments[sequence]):
            complete_data = b"".join(self.fragments[sequence])
            del self.fragments[sequence]
            self._process_packet(sequence, complete_data)

    def _process_packet(self, sequence: int, data: bytes) -> None:
        if self.process_packet_callback(data):
            self.received_packets[sequence % self.received_packets_buffer_size] = (
                Packet(sequence, data)
            )
            self.acks.append(sequence)
            if len(self.acks) > self.ack_buffer_size:
                self.acks.pop(0)

    def _process_acks(self, ack: int, ack_bits: int) -> None:
        for i in range(32):
            if ack_bits & (1 << i):
                acked_sequence = (ack - i) % 65536
                sent_packet = self.sent_packets[
                    acked_sequence % self.sent_packets_buffer_size
                ]
                if sent_packet and sent_packet.sequence == acked_sequence:
                    self._update_stats(sent_packet)

    def _update_stats(self, acked_packet: Packet) -> None:
        current_time = time.time()
        rtt = current_time - acked_packet.send_time
        self.rtt = (
            self.rtt * (1 - self.rtt_smoothing_factor) + rtt * self.rtt_smoothing_factor
        )

        # Update other stats (packet loss, bandwidth) here

    def send_packet(self, data: bytes) -> None:
        if len(data) > self.max_packet_size:
            self._send_fragmented(data)
        else:
            self._send_single(data)

    def _send_single(self, data: bytes) -> None:
        sequence = self._next_sequence()
        ack, ack_bits = self._get_ack_data()

        header = struct.pack("!HHI", sequence, ack, ack_bits)
        packet = header + data

        self.sock.sendto(packet, self.sock.getpeername())
        self.sent_packets[sequence % self.sent_packets_buffer_size] = Packet(
            sequence, data
        )

    def _send_fragmented(self, data: bytes) -> None:
        sequence = self._next_sequence()
        fragments = [
            data[i : i + self.fragment_size]
            for i in range(0, len(data), self.fragment_size)
        ]

        for i, fragment in enumerate(fragments):
            ack, ack_bits = self._get_ack_data()
            header = struct.pack("!HHIBB", sequence, ack, ack_bits, i, len(fragments))
            packet = header + fragment
            self.sock.sendto(packet, self.sock.getpeername())

        self.sent_packets[sequence % self.sent_packets_buffer_size] = Packet(
            sequence, data
        )

    def _next_sequence(self) -> int:
        sequence = self.sequence
        self.sequence = (self.sequence + 1) % 65536
        return sequence

    def _get_ack_data(self) -> Tuple[int, int]:
        if not self.acks:
            return 0, 0

        ack = self.acks[-1]
        ack_bits = 0
        for i, seq in enumerate(reversed(self.acks)):
            if i >= 32:
                break
            if (ack - seq) % 65536 < 32:
                ack_bits |= 1 << ((ack - seq) % 32)

        return ack, ack_bits

    def update(self) -> None:
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # Update RTT, packet loss, and bandwidth statistics here

    def get_stats(self) -> dict:
        return {
            "rtt": self.rtt,
            "packet_loss": self.packet_loss,
            "sent_bandwidth": self.sent_bandwidth,
            "received_bandwidth": self.received_bandwidth,
            "acked_bandwidth": self.acked_bandwidth,
        }


# Example usage:
if __name__ == "__main__":
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("localhost", 12345))
    sock.connect(("localhost", 54321))

    def process_packet(data: bytes) -> bool:
        print(f"Received: {data.decode()}")
        return True

    endpoint = ReliableEndpoint(sock, process_packet_callback=process_packet)
    endpoint.start()

    try:
        while True:
            message = input("Enter message to send: ")
            endpoint.send_packet(message.encode())
            endpoint.update()
            print(endpoint.get_stats())
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        endpoint.stop()
        sock.close()
