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
print("HB OK status=%d" % hb.system_status, flush=True)

def arm():
    conn.mav.command_long_send(1, 1, ac.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                               1.0, 21196.0, 0, 0, 0, 0, 0)
    print(">>ARM_SENT", flush=True)

arm()
t0 = time.time()
status = None
ekf = None
while time.time() - t0 < 5:
    m = conn.recv_match(blocking=True, timeout=0.3)
    if m is None:
        continue
    t = m.get_type()
    if t == "COMMAND_ACK":
        print("ACK cmd=%d res=%d" % (m.command, m.result), flush=True)
    elif t == "SYS_STATUS":
        status = m
    elif t == "EKF_STATUS_REPORT":
        ekf = m
    elif t == "STATUSTEXT":
        print("  TXT: %s" % m.text, flush=True)
    elif t == "EXTENDED_SYS_STATE":
        pass

if status is not None:
    def bit(v, b): return "1" if v & (1 << b) else "0"
    # sensor health bits of interest
    keys = ["accel0", "gyro0", "mag0", "baro0", "gps0", "ekf_att", "ekf_vel",
            "ekf_pos", "ekf_hgt", "opt", "ekf_yaw", "airspeed"]
    bits = [0, 4, 8, 12, 16, 20, 21, 22, 23, 24, 25, 27]
    pl = " ".join("%s=%s" % (k, bit(status.onboard_control_sensors_health, b))
                  for k, b in zip(keys, bits))
    print("SYS health: %s" % pl, flush=True)

if ekf is not None:
    print("EKF flags=0x%x velvar=%.6f posvar=%.6f hgtvar=%.6f compvar=%.6f" %
          (ekf.flags, ekf.velocity_variance, ekf.pos_horiz_variance,
           ekf.terrain_alt_variance if hasattr(ekf, "terrain_alt_variance") else ekf.pos_vert_variance,
           ekf.compass_variance), flush=True)