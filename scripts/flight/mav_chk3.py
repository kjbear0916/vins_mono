#!/usr/bin/env python3
import socket, time

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("127.0.0.1", 14552))
s.settimeout(2)

payload = bytes([6, 8, 0, 0, 0, 0, 0, 0, 0, 3])
t0 = time.time()
seen = {}
last_send = 0
while time.time() - t0 < 12:
    if time.time() - last_send > 2:
        for p in (18570, 14580):
            s.sendto(bytes([0xFE, 9, int(time.time()) & 0xFF, 255, 190]) + payload + b"\x00\x00", ("127.0.0.1", p))
        last_send = time.time()
    try:
        d, addr = s.recvfrom(2048)
        if d[0] == 0xFD:
            msgid = d[5] | (d[6] << 8) | (d[7] << 16)
            lib = "v2"
        elif d[0] == 0xFE:
            msgid = d[5] | (d[6] << 8)
            lib = "v1"
        else:
            continue
        key = (lib, msgid)
        seen.setdefault(key, 0)
        seen[key] += 1
        sysid = d[4] if d[0] == 0xFE else d[3] + (d[4] << 8)
        if key[1] == 0:
            print("HEARTBEAT sysid=%d compid=%d armed_bit=%d" % (sysid, d[6] if d[0] == 0xFE else d[5] + (d[6] << 8), 0), flush=True)
    except socket.timeout:
        pass
# map known px4 msg ids
known = {30: "ATTITUDE", 24: "GPS_RAW_INT", 32: "LOCAL_POSITION_NED", 84: "GLOBAL_POSITION_INT",
         0: "HEARTBEAT", 253: "STATUSTEXT", 74: "VFR_HUD", 81: "RC_CHANNELS", 22: "SERVO_OUTPUT_RAW"}
print("seen:", {("%s#%s" % (k[0], known.get(k[1], k[1]))): v for k, v in seen.items()}, flush=True)