#!/usr/bin/env python3
import pymavlink.mavutil as mavutil
import pymavlink.dialects.v20.ardupilotmega as ac

conn = mavutil.mavlink_connection("udpin:127.0.0.1:14550", dialect="ardupilotmega")
conn.mav.heartbeat_send(ac.MAV_TYPE_GCS, ac.MAV_AUTOPILOT_INVALID, 0, 0, 0)
types = {}
for i in range(12):
    m = conn.recv_match(blocking=True, timeout=2)
    if m is None:
        continue
    t = m.get_type()
    types[t] = types.get(t, 0) + 1
    if t == "HEARTBEAT":
        print("HB src=%d armed=%d mode=0x%x" % (m.get_srcSystem(),
            (m.base_mode & ac.MAV_MODE_FLAG_SAFETY_ARMED) and 1 or 0, m.base_mode), flush=True)
        break
print("seen:", types, flush=True)