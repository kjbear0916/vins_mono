#!/usr/bin/env python3
"""Parse a UDP pcap, print every unique (srcIP.srcPort->dstIP.dstPort) pair
with message-id histogram, grouped. Decides: is PX4 sending to 127.0.0.1
or to a non-loopback IP (163.0.0.x by default in this sitl engine)?"""
import struct
import sys
from collections import Counter, defaultdict

path = sys.argv[1]
blob = open(path, "rb").read()

cur = {"sip": None, "sport": None, "dip": None, "dport": None}
flow = Counter()
first_in_flow = {}
t = [0.0]

def emit():
    k = "%s:%s -> %s:%s" % (cur["sip"], cur["sport"], cur["dip"], cur["dport"])
    flow[k] += 1
    first_in_flow.setdefault(k, t[0])

i = 0
n = len(blob)
link_type = None
pkt = 0
while i < n:
    if i == 0:
        magic = blob[i:i+4]
        if magic == b"\xd4\xc3\xb2\xa1" or magic == b"\xa1\xb2\xc3\xd4":
            link_type = None
            # global header 24 bytes
            i = 24
            continue
        else:
            # produced by 'w' option of tcpdump -> pcap already
            i = 0
    # pcap per-packet header (16 bytes) if we're not in pcapng
    if link_type is None:
        # try to detect: tcpdump -w produces pcap. locate 'lt' assume classic
        # jump to first record: need magic at very start handled above
        pass
    # classic pcap record
    if i + 16 > n:
        break
    ts_sec, ts_usec, incl, orig = struct.unpack_from("<IIII", blob, i)
    i += 16
    if i + incl > n:
        break
    frame = blob[i:i+incl]
    i += incl
    pkt += 1
    t[0] = ts_sec + ts_usec * 1e-6
    if len(frame) < 14:
        continue
    eth = None
    if link_type is None:
        # Ethernet: dst(6) src(6) ethertype(2)
        ethertype = struct.unpack_from(">H", frame, 12)[0]
        if ethertype == 0x0800:
            ip = frame[14:]
        else:
            continue
    else:
        ip = frame
    if len(ip) < 20:
        continue
    ver = ip[0] >> 4
    if ver != 4:
        continue
    ihl = (ip[0] & 0x0F) * 4
    proto = ip[9]
    if proto != 17:  # UDP
        continue
    sip = ".".join(str(b) for b in ip[12:16])
    dip = ".".join(str(b) for b in ip[16:20])
    sport, dport = struct.unpack_from(">HH", ip, ihl)
    payload = ip[ihl+8:]
    cur = {"sip": sip, "sport": sport, "dip": dip, "dport": dport}
    emit()

print("pcap=%s pkts=%d elapsed=%.1fs" % (path, pkt, t[0]))
print("flow : count : first_t")
for k, n in flow.most_common():
    print("%-40s %5d  %8.1f" % (k, n, first_in_flow[k]))
