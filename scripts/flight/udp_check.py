#!/usr/bin/env python3
import pymavlink.mavutil as mavutil
import pymavlink.dialects.v20.ardupilotmega as ac

conn = mavutil.mavlink_connection("udpin:127.0.0.1:14540", dialect="ardupilotmega")
conn.mav.heartbeat_send(ac.MAV_TYPE_GCS, ac.MAV_AUTOPILOT_INVALID, 0, 0, 0)
for i in range(3):
    m = conn.recv_match(blocking=True, timeout=2)
    print("got", m.get_type() if m else None, flush=True)