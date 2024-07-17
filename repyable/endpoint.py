import random
import socket
import struct
import time

from repyable import MAX_PACKET_SIZE

MAX_CLIENTS = 64
TIMEOUT = 5.0
PACKET_SALT_SIZE = 8


class Packet:
    CONNECTION_REQUEST = 0
    CHALLENGE = 1
    CHALLENGE_RESPONSE = 2
    CONNECTION_ACCEPTED = 3
    CONNECTION_DENIED = 4
    PAYLOAD = 5
    DISCONNECT = 6

    @staticmethod
    def pack(packet_type, client_salt, server_salt, payload=b""):
        return struct.pack("!BQQ", packet_type, client_salt, server_salt) + payload

    @staticmethod
    def unpack(data):
        packet_type, client_salt, server_salt = struct.unpack("!BQQ", data[:17])
        return packet_type, client_salt, server_salt, data[17:]


class Client:
    def __init__(self, server_address):
        self.server_address = server_address
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.state = "disconnected"
        self.client_salt = random.randint(0, 2**64 - 1)
        self.server_salt = 0
        self.last_packet_time = 0

    def connect(self):
        self.state = "connecting"
        self.send_connection_request()

    def send_connection_request(self):
        packet = Packet.pack(Packet.CONNECTION_REQUEST, self.client_salt, 0)
        self.socket.sendto(packet, self.server_address)

    def send_challenge_response(self, challenge):
        packet = Packet.pack(Packet.CHALLENGE_RESPONSE, self.client_salt, challenge)
        self.socket.sendto(packet, self.server_address)

    def send_payload(self, payload):
        packet = Packet.pack(
            Packet.PAYLOAD, self.client_salt, self.server_salt, payload
        )
        self.socket.sendto(packet, self.server_address)

    def disconnect(self):
        if self.state == "connected":
            packet = Packet.pack(Packet.DISCONNECT, self.client_salt, self.server_salt)
            for _ in range(10):
                self.socket.sendto(packet, self.server_address)
        self.state = "disconnected"

    def update(self):
        if self.state == "disconnected":
            return

        try:
            data, addr = self.socket.recvfrom(1024)
            packet_type, client_salt, server_salt, payload = Packet.unpack(data)

            if packet_type == Packet.CHALLENGE and self.state == "connecting":
                self.server_salt = server_salt
                self.send_challenge_response(server_salt)
                self.state = "challenging"
            elif (
                packet_type == Packet.CONNECTION_ACCEPTED
                and self.state == "challenging"
            ):
                self.state = "connected"
                print("Connected to server")
            elif packet_type == Packet.CONNECTION_DENIED:
                self.state = "disconnected"
                print("Connection denied")
            elif packet_type == Packet.PAYLOAD and self.state == "connected":
                print(f"Received payload: {payload.decode()}")
            elif packet_type == Packet.DISCONNECT and self.state == "connected":
                self.state = "disconnected"
                print("Server disconnected")

            self.last_packet_time = time.time()
        except socket.error:
            pass

        if time.time() - self.last_packet_time > TIMEOUT:
            self.state = "disconnected"
            print("Connection timed out")


class Server:
    def __init__(self, address):
        self.address = address
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(address)
        self.clients = {}
        self.pending_clients = {}

    def find_free_client_slot(self):
        return None if len(self.clients) >= MAX_CLIENTS else len(self.clients)

    def update(self):
        try:
            data, addr = self.socket.recvfrom(1024)
            packet_type, client_salt, server_salt, payload = Packet.unpack(data)

            if packet_type == Packet.CONNECTION_REQUEST:
                self.handle_connection_request(addr, client_salt)
            elif packet_type == Packet.CHALLENGE_RESPONSE:
                self.handle_challenge_response(addr, client_salt, server_salt)
            elif packet_type == Packet.PAYLOAD:
                self.handle_payload(addr, client_salt, server_salt, payload)
            elif packet_type == Packet.DISCONNECT:
                self.handle_disconnect(addr, client_salt, server_salt)
        except socket.error:
            pass

        self.check_timeouts()

    def handle_connection_request(self, addr, client_salt):
        if addr not in self.pending_clients and addr not in self.clients:
            if self.find_free_client_slot() is not None:
                challenge = random.randint(0, 2**64 - 1)
                self.pending_clients[addr] = {
                    "client_salt": client_salt,
                    "server_salt": challenge,
                    "time": time.time(),
                }
                packet = Packet.pack(Packet.CHALLENGE, client_salt, challenge)
                self.socket.sendto(packet, addr)
            else:
                packet = Packet.pack(Packet.CONNECTION_DENIED, client_salt, 0)
                self.socket.sendto(packet, addr)

    def handle_challenge_response(self, addr, client_salt, server_salt):
        if addr in self.pending_clients:
            pending = self.pending_clients[addr]
            if (
                pending["client_salt"] == client_salt
                and pending["server_salt"] == server_salt
            ):
                slot = self.find_free_client_slot()
                if slot is not None:
                    self.clients[addr] = {
                        "client_salt": client_salt,
                        "server_salt": server_salt,
                        "time": time.time(),
                    }
                    packet = Packet.pack(
                        Packet.CONNECTION_ACCEPTED,
                        client_salt,
                        server_salt,
                        struct.pack("!I", slot),
                    )
                    self.socket.sendto(packet, addr)
                    del self.pending_clients[addr]
                else:
                    packet = Packet.pack(
                        Packet.CONNECTION_DENIED, client_salt, server_salt
                    )
                    self.socket.sendto(packet, addr)

    def handle_payload(self, addr, client_salt, server_salt, payload):
        if addr in self.clients:
            client = self.clients[addr]
            if (
                client["client_salt"] == client_salt
                and client["server_salt"] == server_salt
            ):
                client["time"] = time.time()
                print(f"Received payload from {addr}: {payload.decode()}")
                # Echo the payload back to the client
                packet = Packet.pack(Packet.PAYLOAD, client_salt, server_salt, payload)
                self.socket.sendto(packet, addr)

    def handle_disconnect(self, addr, client_salt, server_salt):
        if addr in self.clients:
            client = self.clients[addr]
            if (
                client["client_salt"] == client_salt
                and client["server_salt"] == server_salt
            ):
                del self.clients[addr]
                print(f"Client {addr} disconnected")

    def check_timeouts(self):
        current_time = time.time()
        for addr in list(self.pending_clients.keys()):
            if current_time - self.pending_clients[addr]["time"] > TIMEOUT:
                del self.pending_clients[addr]

        for addr in list(self.clients.keys()):
            if current_time - self.clients[addr]["time"] > TIMEOUT:
                del self.clients[addr]
                print(f"Client {addr} timed out")


# Example usage
if __name__ == "__main__":
    server = Server(("localhost", 12345))
    print("Server started on localhost:12345")

    while True:
        server.update()
        time.sleep(0.01)  # Small delay to prevent busy-waiting

# Client usage example:
# client = Client(('localhost', 12345))
# client.connect()
#
# while True:
#     client.update()
#     if client.state == "connected":
#         client.send_payload(b"Hello, server!")
#     time.sleep(0.1)
#
# client.disconnect()
