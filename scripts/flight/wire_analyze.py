#!/usr/bin/env python3
"""Parse a pcap captured by `tcpdump -i any` (DLT_LINUX_SLL=113, EN10MB=1 or NULL=0).
Answer: does PX4's UDP *heartbeat/stream* traffic target 127.0.0.1
(the loopback we bind) or a NON-loopback IP? Also for EACH MAVLink link
(14550 = GCS, 14540 = onboard) print the actual destination IP:port.

Usage: python3 wire_analyze.py /tmp/wire60.pcap
"""
import struct
import sys
from collections import Counter

raw = open(sys.argv[1], "rb").read()
magic = raw[:4]
if magic not in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\x4d\x3c\xb2\xa1"):
    print("not classic pcap:", magic)
    sys.exit(2)

link = struct.unpack("<I", raw[20:24])[0]
print("linktype=%d" % link)
i = 24
n = len(raw)
pkt = 0
lo_dst = nonlo_dst = 0
flows = Counter()
by_dstport = Counter()
t0 = None
while i + 16 <= n:
    ts, tus, incl, orig = struct.unpack("<IIII", raw[i:i+16])
    i += 16
    if i + incl > n:
        break
    fr = raw[i:i+incl]
    i += incl
    pkt += 1
    # --- layer 2 ---
    if link == 113:            # Linux cooked capture: 16B header
        proto = struct.unpack(">H", fr[14:16])[0]
        ip = fr[16:]
    elif link == 1:            # Ethernet
        proto = struct.unpack(">H", fr[12:14])[0]
        ip = fr[14:]
    elif link == 0:            # NULL loopback (4B family)
        proto = struct.unpack(">I", fr[:4])[0]
        ip = fr[4:]
    else:
        print("unhandled linktype", link)
        sys.exit(2)
    if proto != 0x0800:
        continue
    if len(ip) < 20 or (ip[0] >> 4) != 4:
        continue
    ihl = (ip[0] & 0x0F) * 4
    if ip[9] != 17:            # UDP only
        continue
    sip = ".".join(str(x) for x in ip[12:16])
    dip = ".".join(str(x) for x in ip[16:20])
    sport, dport = struct.unpack(">HH", ip[ihl:ihl+4])
    if dport not in (14540, 14550, 14580, 18570):
        continue
    key = "%s:%d->%s:%d" % (sip, sport, dip, dport)
    flows[key] += 1
    if dip == "127.0.0.1":
        lo_dst += 1
    else:
        nonlo_dst += 1
    by_dstport[dport] += 1

print("pkts=%d lo_dst=%d nonlo_dst=%d" % (pkt, lo_dst, nonlo_dst))
print("== flow (count) ==")
for k, v in flows.most_common():
    print("  %6d  %s" % (v, k))
print("== by dstport ==")
for k, v in by_dstport.most_common():
    print("  dstport %-6d %d" % (k, v))
verdict = "127.0.0.1-BIND-CORRECT" if nonlo_dst == 0 else "PX4-SENDS-TO-NONLOOP->BIND-0.0.0.0"
print("VERDICT", verdict)
