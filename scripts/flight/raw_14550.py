#!/usr/bin/env python3
import socket, time

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 14550))
s.settimeout(10)

print("Listening on 0.0.0.0:14550 for 10s...", flush=True)
t0 = time.time()
count = 0
while time.time() - t0 < 10:
    try:
        data, addr = s.recvfrom(4096)
        count += 1
        hdr = data[0] if data else 0
        msgid = -1
        if hdr == 0xFD and len(data) >= 10:
            msgid = data[7] | (data[8] << 8) | (data[9] << 16)
        elif hdr == 0xFE and len(data) >= 6:
            msgid = data[5] | (data[6] << 8)
        known = {0: "HEARTBEAT", 30: "ATTITUDE", 32: "LOCAL_POS", 84: "GLOBAL_POS"}
        print("t=%.1fs pkt#%d len=%d hdr=0x%02x msgid=%d %s from %s" %
              (time.time()-t0, count, len(data), hdr, msgid, known.get(msgid, "?"), addr), flush=True)
    except socket.timeout:
        print("(timeout after %.1fs, got %d packets total)" % (time.time()-t0, count), flush=True)
        break
s.close()
print("total packets: %d" % count, flush=True)
