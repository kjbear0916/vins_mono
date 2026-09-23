#!/usr/bin/env python3
"""Async UDP sinks on BOTH links that mirror the Google-Monitor policy (bind
0.0.0.0 + SO_REUSEADDR) and, with the companion speaking, verify:
  * heartbeat arrives on the bound socket
  * streams are full-rate for the whole window (no second-0 collapse)
Logs once per type + a 1-min heartbeat trace.
"""
import os
import socket
import struct
import threading
import time

BIND = "0.0.0.0"   # exactly like the raw monitor that provably received
PORTS = (14550, 14540)
DUR = 70

MSGID = {0: "HEARTBEAT", 1: "SYS_STATUS", 2: "SYSTEM_TIME", 3: "PING",
         24: "GPS_RAW_INT", 30: "ATTITUDE", 32: "LOCAL_POSITION_NED",
         33: "GLOBAL_POSITION_INT", 65: "RC_CHANNELS", 74: "VFR_HUD",
         84: "ATTITUDE_QUATERNION", 87: "EXTENDED_SYS_STATE",
         204: "SERVO_OUTPUT_RAW_0", 253: "STATUSTEXT"}

evt = threading.Event()


def listen(port, tag):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT if hasattr(socket, "SO_REUSEPORT") else -1, 1)
    try:
        s.bind((BIND, port))
        bound = "BOUND_%s" % port
    except OSError as e:
        print(tag, "BIND_FAIL", e, flush=True)
        return
    print(tag, bound, flush=True)
    t0 = time.time()
    hb_n = 0
    counts = {}
    last_hb_t = [0.0]
    while time.time() - t0 < DUR:
        data, addr = s.recvfrom(4096)
        mid = data[5] if len(data) > 5 and data[2] == 0xfd else -1
        counts[mid] = counts.get(mid, 0) + 1
        if mid == 0:
            hb_n += 1
            last_hb_t[0] = time.time() - t0
    print(tag, "END total=%d hb=%d last_hb_t=%.1fs msgids=%s" % (
        sum(counts.values()), hb_n, last_hb_t[0],
        {MSGID.get(k, k): v for k, v in sorted(counts.items()) if v}), flush=True)


def hb_broadcast():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((BIND, 0))
    t0 = time.time()
    while time.time() - t0 < DUR:
        # minimal MAVLink v2 HEARTBEAT crc (common/msg id 0) - 9 bytes payload
        # seq=8, sysid=255, compid=197 (GCS), type=6 GCS, autopilot=8, mode=0, custom=0, state=4
        # raw bytes minimal - PX4 uses srcSystem/srcComponent from UDP port only loosely
        hb = bytes([0xFD, 9, 8, 255, 197, 0, 50, 0, 0, 0, 0, 0, 0x03, 0x8F])
        try:
            s.sendto(hb, ("127.0.0.1", 18570))
        except Exception:
            pass
        time.sleep(1)
