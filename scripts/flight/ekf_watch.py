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

conn.mav.command_long_send(1, 1, ac.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                           ac.MAVLINK_MSG_ID_EKF_STATUS_REPORT, 500000, 0, 0, 0, 0, 0)

t0 = time.time()
last = 0
while time.time() - t0 < 70:
    m = conn.recv_match(blocking=True, timeout=1.0)
    if m is None:
        continue
    t = m.get_type()
    if t != "EKF_STATUS_REPORT":
        continue
    now = int(time.time() - t0)
    if now == last:
        continue
    last = now
    flags = m.flags
    names = ["att", "vel_h", "vel_v", "pos_h", "pos_v", "terr", "const_pos", "pred_pos_h"]
    bit = lambda i: "1" if flags & (1 << i) else "0"
    print("t=%02ds flags 0x%03x %s velvar=%.5f posvar=%.5f compvar=%.5f" %
          (now, flags, " ".join("%s=%s" % (n, bit(i)) for i, n in enumerate(names)),
           m.velocity_variance, m.pos_horiz_variance, m.compass_variance), flush=True)