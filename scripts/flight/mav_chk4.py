#!/usr/bin/env python3
import socket, time

# Dual-socket GCS: bind 14550 to receive, send via ephemeral port to 18570
rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rx.bind(("127.0.0.1", 14550))
tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
tx.bind(("127.0.0.1", 0))
rx.settimeout(3)
tx.settimeout(3)

# MAVLink v1 framer
seq = 0
def frame_v1(msgid, payload, sysid=255, compid=190):
    global seq
    msg = bytes([0xFE, len(payload), seq & 0xFF, sysid, compid, msgid & 0xFF, (msgid >> 8) & 0xFF]) + payload
    msg += b"\x00\x00"  # no CRC calc (px4 tolerant? may drop)
    seq += 1
    return msg

# send GCS heartbeat
hb = frame_v1(0, bytes([6, 8, 0, 0, 0, 0, 0, 0, 0, 3]))
print("send hb to 18570", flush=True)
tx.sendto(hb, ("127.0.0.1", 18570))
tx.sendto(hb, ("127.0.0.1", 14580))

seen = {}
t0 = time.time()
while time.time() - t0 < 10:
    try:
        d, addr = rx.recvfrom(2048)
        if d[0] == 0xFD:
            sysid = d[3] + (d[4] << 8)
            compid = d[5] + (d[6] << 8)
            msgid = d[7] | (d[8] << 8) | (d[9] << 16)
            plen = d[1]
        elif d[0] == 0xFE:
            sysid = d[3]
            compid = d[4]
            msgid = d[5] | (d[6] << 8)
            plen = d[1]
        else:
            continue
        seen[msgid] = seen.get(msgid, 0) + 1
        if msgid == 0:
            print("HEARTBEAT from sys=%d comp=%d via %s" % (sysid, compid, addr), flush=True)
        else:
            known = {30: "ATTITUDE", 32: "LOCAL_POSITION_NED", 84: "GLOBAL_POSITION_INT"}
            print("rx msgid=%d %s" % (msgid, known.get(msgid, "?")), flush=True)
    except socket.timeout:
        print("(rx timeout)", flush=True)
print("seen:", seen, flush=True)
# also try reading on ephemeral-bound sending socket for replies
ts = time.time()
while time.time() - ts < 4:
    try:
        d, addr = tx.recvfrom(2048)
        print("tx-socket got msgid=%d from %s" % (d[5] | (d[6] << 8), addr), flush=True)
    except socket.timeout:
        break