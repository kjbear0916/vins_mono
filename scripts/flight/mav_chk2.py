#!/usr/bin/env python3
import socket, time, struct

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("127.0.0.1", 14551))
s.settimeout(2)

payload = struct.pack("<BBBBBBIBBH", 6, 8, 0, 0, 0, 0, 0, 0, 0, 3)
def mav1_heartbeat(seq):
    return bytes([0xFE, 9, seq & 0xFF, 255, 190]) + payload + struct.pack("<H", 0)

def send_hb(seq):
    # send GCS heartbeat (sysid255) to every px4 local port
    for p in (18570, 14580, 14280, 13030):
        s.sendto(mav1_heartbeat(seq), ("127.0.0.1", p))
    return mav1_heartbeat(seq)

ids = {}
t0 = time.time()
last_send = 0
while time.time() - t0 < 10:
    # resend heartbeat every 2s
    now = time.time()
    if now - last_send > 2:
        send_hb(int(now))
        last_send = now
        print("HB sent", flush=True)
    try:
        d, addr = s.recvfrom(2048)
        if d[0] == 0xFD:  # v2
            msgid = d[5] | (d[6] << 8) | (d[7] << 16)
            ids[msgid] = ids.get(msgid, 0) + 1
        elif d[0] == 0xFE:
            msgid = d[5] | (d[6] << 8)
            ids[msgid] = ids.get(msgid, 0) + 1
    except socket.timeout:
        print("(t)", end="", flush=True)
print("")
print("ids:", sorted(set(ids.items())), flush=True)