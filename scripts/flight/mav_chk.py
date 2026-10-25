#!/usr/bin/env python3
import socket, time, struct

# send GCS heartbeat to px4 GCS local port 18570, then listen on 14550
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("127.0.0.1", 14550))

# MAVLink v1 heartbeat (sysid 255, compid 190) - type=6 GCS, autopilot=8 INVALID
# custom mode 0, base mode 0, system status 0, mavlink version 3
payload = struct.pack("<BBBBBBIBBH",
    6, 8, 0, 0, 0, 0, 0, 0, 0, 3)
seq = 0
def mav_msg(msgid, payload_bytes):
    global seq
    l = len(payload_bytes)
    if l != 253:
        # MAVLink v1 framing
        return bytes([0xFE, l, seq, 255, 190]) + payload_bytes + struct.pack("<H", 0)
    else:
        return bytes([0xFD, l, 0, seq, 255, 190]) + payload_bytes + struct.pack("<H", 0)
seq += 1
hb = mav_msg(0, payload)
s.sendto(hb, ("127.0.0.1", 18570))
print("sent HB 62 bytes to 18570", flush=True)

s.settimeout(5)
samples = []
t0 = time.time()
while time.time() - t0 < 8:
    try:
        d, addr = s.recvfrom(2048)
        if d and d[0] == 0xFE and len(d) >= 8:
            msgid = d[5] | (d[6] << 8)
            samples.append(msgid)
            print("got id=%d len=%d from %s" % (msgid, len(d), addr), flush=True)
        elif d:
            print("got raw len=%d hdr=%02x" % (len(d), d[0]), flush=True)
    except socket.timeout:
        print("timeout", flush=True)
        break
print("msgids:", sorted(set(samples)), flush=True)