import socket
import struct
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from repyable import MAX_PACKET_SIZE
from repyable.circular_buffer import CircularBuffer

# Format: sequence (2 bytes), ack (2 bytes), ack_bits (4 bytes)
HEADER_FORMAT = "!HHI"

# Format: fragment_id (1 byte), total_fragments (1 byte)
FRAGMENT_FOOTER_FORMAT = "!BB"

# Format: sequence (2 bytes), ack (2 bytes), ack_bits (4 bytes)
# fragment_id (1 byte), total_fragments (1 byte)
FRAGMENT_FORMAT = "!HHIBB"


@dataclass
class Packet:
    sequence: int
    data: bytes
    send_time: float = field(default_factory=time.time)


class ReliableEndpoint:
    def __init__(
        self,
        sock: socket.socket,
        max_packet_size: int = MAX_PACKET_SIZE,
        fragment_above: int = 1000,
        max_fragments: int = 16,
        fragment_size: int = 500,
        buffer_size: int = 256,
        ack_buffer_size: int = 32,
        rtt_smoothing_factor: float = 0.1,
        packet_loss_smoothing_factor: float = 0.1,
        bandwidth_smoothing_factor: float = 0.1,
        process_packet_callback: Callable[[bytes], bool] = lambda x: True,
    ) -> None:
        self.sock = sock
        self.max_packet_size = max_packet_size
        self.fragment_above = fragment_above
        self.max_fragments = max_fragments
        self.fragment_size = fragment_size
        self.ack_buffer_size = ack_buffer_size
        self.rtt_smoothing_factor = rtt_smoothing_factor
        self.packet_loss_smoothing_factor = packet_loss_smoothing_factor
        self.bandwidth_smoothing_factor = bandwidth_smoothing_factor
        self.process_packet_callback = process_packet_callback

        self.sequence: int = 0
        self.acks: list[int] = []
        self.sent_packets: CircularBuffer[Packet] = CircularBuffer(buffer_size)
        self.received_packets: CircularBuffer[Packet] = CircularBuffer(buffer_size)
        self.fragments: dict[int, list[bytes | None]] = {}

        self.rtt: float = 0.0
        self.packet_loss: float = 0.0
        self.sent_bandwidth: float = 0.0
        self.received_bandwidth: float = 0.0
        self.acked_bandwidth: float = 0.0

        self.last_update_time: float = time.time()
        self.running: bool = False
        self.receive_thread: threading.Thread | None = None

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
            self._update()
            try:
                data, addr = self.sock.recvfrom(self.max_packet_size)
                self._process_received_data(data)
            except TimeoutError:
                pass

    def _process_received_data(self, data: bytes) -> None:
        sequence, ack, ack_bits = struct.unpack(HEADER_FORMAT, data[:8])
        payload = data[8:]

        if len(payload) > self.fragment_above:
            self._process_fragment(sequence, payload)
        else:
            self._process_packet(sequence, payload)

        self._process_acks(ack, ack_bits)

    def _process_fragment(self, sequence: int, data: bytes) -> None:
        fragment_id, total_fragments = struct.unpack(FRAGMENT_FOOTER_FORMAT, data[:2])
        fragment_data = data[2:]

        if sequence not in self.fragments:
            self.fragments[sequence] = [None] * total_fragments

        self.fragments[sequence][fragment_id] = fragment_data

        if all(self.fragments[sequence]):
            complete_data = b"".join(
                fragment
                for fragment in self.fragments[sequence]
                if fragment is not None
            )
            del self.fragments[sequence]
            self._process_packet(sequence, complete_data)

    def _process_packet(self, sequence: int, data: bytes) -> None:
        if self.process_packet_callback(data):
            self.received_packets.push(Packet(sequence, data))
            self.acks.append(sequence)
            if len(self.acks) > self.ack_buffer_size:
                self.acks.pop(0)

    def _process_acks(self, ack: int, ack_bits: int) -> None:
        for i in range(32):
            if ack_bits & (1 << i):
                acked_sequence = (ack - i) % 65536
                for j in range(len(self.sent_packets)):
                    if self.sent_packets[j].sequence == acked_sequence:
                        self._update_rtt(self.sent_packets[j])
                        break

    def _update_rtt(self, acked_packet: Packet) -> None:
        current_time = time.time()
        rtt = current_time - acked_packet.send_time
        self.rtt = (
            self.rtt * (1 - self.rtt_smoothing_factor) + rtt * self.rtt_smoothing_factor
        )

    def send_packet(self, data: bytes) -> None:
        if len(data) > self.max_packet_size:
            self._send_fragmented(data)
        else:
            self._send_single(data)

    def _send_single(self, data: bytes) -> None:
        sequence = self._next_sequence()
        ack, ack_bits = self._get_ack_data()

        header = struct.pack(HEADER_FORMAT, sequence, ack, ack_bits)
        packet = header + data

        self.sock.sendto(packet, self.sock.getpeername())
        self.sent_packets.push(Packet(sequence, data))

    def _send_fragmented(self, data: bytes) -> None:
        sequence = self._next_sequence()
        fragments = [
            data[i : i + self.fragment_size]
            for i in range(0, len(data), self.fragment_size)
        ]

        for i, fragment in enumerate(fragments):
            ack, ack_bits = self._get_ack_data()

            header = struct.pack(
                FRAGMENT_FORMAT, sequence, ack, ack_bits, i, len(fragments)
            )
            packet = header + fragment
            self.sock.sendto(packet, self.sock.getpeername())

        self.sent_packets.push(Packet(sequence, data))

    def _next_sequence(self) -> int:
        sequence = self.sequence
        self.sequence = (self.sequence + 1) % 65536
        return sequence

    def _get_ack_data(self) -> tuple[int, int]:
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

    def _update(self) -> None:
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # Update packet loss
        acked_packets = sum(
            1
            for packet in self.sent_packets
            if packet is not None and packet.send_time <= current_time - self.rtt
        )
        total_packets = sum(1 for packet in self.sent_packets if packet is not None)
        if total_packets > 0:
            current_packet_loss = 1 - (acked_packets / total_packets)
            self.packet_loss = (
                self.packet_loss * (1 - self.packet_loss_smoothing_factor)
                + current_packet_loss * self.packet_loss_smoothing_factor
            )

        # Update bandwidth statistics
        sent_bytes = sum(
            len(packet.data)
            for packet in self.sent_packets
            if packet is not None and packet.send_time > current_time - dt
        )
        received_bytes = sum(
            len(packet.data)
            for packet in self.received_packets
            if packet is not None and packet.send_time > current_time - dt
        )
        acked_bytes = sum(
            len(packet.data)
            for packet in self.sent_packets
            if packet is not None
            and packet.send_time <= current_time - self.rtt
            and packet.send_time > current_time - dt - self.rtt
        )

        self.sent_bandwidth = (
            self.sent_bandwidth * (1 - self.bandwidth_smoothing_factor)
            + (sent_bytes / dt) * self.bandwidth_smoothing_factor
        )
        self.received_bandwidth = (
            self.received_bandwidth * (1 - self.bandwidth_smoothing_factor)
            + (received_bytes / dt) * self.bandwidth_smoothing_factor
        )
        self.acked_bandwidth = (
            self.acked_bandwidth * (1 - self.bandwidth_smoothing_factor)
            + (acked_bytes / dt) * self.bandwidth_smoothing_factor
        )

    def get_stats(self) -> dict[str, float]:
        return {
            "rtt": self.rtt,
            "packet_loss": self.packet_loss,
            "sent_bandwidth": self.sent_bandwidth,
            "received_bandwidth": self.received_bandwidth,
            "acked_bandwidth": self.acked_bandwidth,
        }

    def _clean_up_old_packets(self, current_time: float) -> None:
        """Clean up old fragments and check for very old packets."""
        timeout = max(self.rtt * 4, 1.0)  # Use at least 1 second timeout

        # Clean up fragments
        self.fragments = {
            seq: frags
            for seq, frags in self.fragments.items()
            if current_time - self._get_packet_send_time(seq) < timeout
        }

        # Check for very old packets (for diagnostics or connection health)
        old_sent_packets = sum(
            1
            for packet in self.sent_packets
            if current_time - packet.send_time > timeout
        )
        old_received_packets = sum(
            1
            for packet in self.received_packets
            if current_time - packet.send_time > timeout
        )

        if old_sent_packets > 0 or old_received_packets > 0:
            print(
                f"Warning: {old_sent_packets} sent and {old_received_packets} received packets are older than {timeout} seconds"
            )

    def _get_packet_send_time(self, sequence: int) -> float:
        """Get the send time of a packet with the given sequence number."""
        for packet in self.sent_packets:
            if packet.sequence == sequence:
                return packet.send_time
        return 0.0  # Return 0 if packet not found


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
            print(endpoint.get_stats())
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        endpoint.stop()
        sock.close()
