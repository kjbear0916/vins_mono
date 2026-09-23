#!/usr/bin/env python3
import pymavlink.mavutil as mavutil
import pymavlink.dialects.v20.ardupilotmega as ac
import time

conn = mavutil.mavlink_connection("udpin:127.0.0.1:14540", dialect="ardupilotmega")
conn.mav.heartbeat_send(ac.MAV_TYPE_GCS, ac.MAV_AUTOPILOT_INVALID, 0, 0, 0)
hb = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=15)
if hb is None:
    print("NO_HB")
    raise SystemExit(1)
print("HB OK sysid=%d comp=%d armed=%d mode=0x%x status=%d" %
      (hb.get_srcSystem(), hb.get_srcComponent(),
       hb.base_mode & ac.MAV_MODE_FLAG_SAFETY_ARMED, hb.base_mode, hb.system_status), flush=True)

t0 = time.time()
fired = False
while time.time() - t0 < 60:
    m = conn.recv_match(blocking=True, timeout=0.5)
    if m is None:
        continue
    t = m.get_type()
    now = time.time() - t0
    if t == "HEARTBEAT":
        if now - (now % 5) < 0.4:
            print("t=%.0fs status=%d armed=%d mode=0x%x" %
                  (now, m.system_status, m.base_mode & ac.MAV_MODE_FLAG_SAFETY_ARMED,
                   m.base_mode), flush=True)
        if not fired and now >= 40.0:
            conn.mav.command_long_send(1, 1, ac.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                                       1.0, 21196.0, 0, 0, 0, 0, 0)
            fired = True
            print(">>ARM_SENT t=%.0fs config=21196" % now, flush=True)
    elif t == "COMMAND_ACK":
        print("ACK cmd=%d res=%d" % (m.command, m.result), flush=True)
    elif t == "STATUSTEXT":
        print("  TXT: %s" % m.text, flush=True)
    elif t == "EXTENDED_SYS_STATE":
        print("EXT landed=%d" % m.landed_state, flush=True)