import struct

HEADER_FORMAT = "!HHL"

# Explanation of the format string:
# '!' - use network byte order (big-endian)
# 'H' - unsigned short (2 bytes) for sequence
# 'H' - unsigned short (2 bytes) for ack
# 'L' - unsigned long (4 bytes) for ack_bits

