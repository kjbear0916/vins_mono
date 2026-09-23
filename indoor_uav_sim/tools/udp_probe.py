#!/usr/bin/env python3
import socket, struct, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("0.0.0.0", 14540))
s.settimeout(8)
start = time.time()
n = 0
try:
    while time.time() - start < 8:
        data, addr = s.recvfrom(65535)
        n += 1
        if n <= 3:
            print(f"from {addr} bytes={len(data)} magic={data[0]:02x} start {data[:6].hex()}")
except socket.timeout:
    pass
print(f"total packets in 8s: {n}")
s.close()