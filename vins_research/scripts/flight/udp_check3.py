#!/usr/bin/env python3
import time
import pymavlink.mavutil as mavutil
import pymavlink.dialects.v20.ardupilotmega as ac

conn = mavutil.mavlink_connection("udpout:127.0.0.1:14580", dialect="ardupilotmega")
print("bound src", conn.port, flush=True)
conn.mav.heartbeat_send(ac.MAV_TYPE_GCS, ac.MAV_AUTOPILOT_INVALID, 0, 0, 0)
types = {}
hb = None
t0 = time.time()
while time.time() - t0 < 10:
    m = conn.recv_match(blocking=True, timeout=1.5)
    if m is None:
        continue
    t = m.get_type()
    types[t] = types.get(t, 0) + 1
    if t == "HEARTBEAT":
        hb = m
        break
print("HB:", hb)
print("seen:", types, flush=True)