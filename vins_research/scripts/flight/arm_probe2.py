#!/usr/bin/env python3
"""Robust link + arm: send our own GCS heartbeat every 1s so PX4 keeps the
GCS link at full rate and recognizes a partner. Resets SYS_HAS_* to 1,
sets OFFBOARD, arms, and dumps arming-denial STATUSTEXT + estimator flags."""
import threading
import time
from pymavlink import mavutil
from pymavlink.dialects.v20 import common as c

TARGET = (1, 1)
conn = mavutil.mavlink_connection("udpin:127.0.0.1:14550")
conn.mav.srcSystem = 255
conn.mav.srcComponent = 0
_heartbeat_running = True


def hb_loop():
    while _heartbeat_running:
        conn.mav.heartbeat_send(
            c.MAV_TYPE_GCS, c.MAV_AUTOPILOT_INVALID,
            c.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 0, c.MAV_STATE_ACTIVE)
        time.sleep(1.0)


threading.Thread(target=hb_loop, daemon=True).start()

print("WAIT_HB", flush=True)
hb = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=15)
if hb is None:
    print("NO_HB", flush=True)
    _heartbeat_running = False
    raise SystemExit(2)
print("HB armed=%d mode=0x%x" % ((hb.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED) and 1 or 0,
                                 hb.base_mode), flush=True)

def set_param(name, val, ptype=c.MAV_PARAM_TYPE_INT32, timeout=3):
    conn.mav.param_set_send(TARGET[0], TARGET[1], name, float(val), ptype)
    conn.mav.param_request_read_send(TARGET[0], TARGET[1], name, -1)
    pv = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=timeout)
    if pv is not None:
        print("P_SET %s=%r" % (name.decode(), pv.param_value), flush=True)
    return pv

for n, v in ((b"SYS_HAS_MAG", 1), (b"SYS_HAS_BARO", 1), (b"SYS_HAS_GPS", 1)):
    set_param(n, v)
    time.sleep(0.5)

print("DIAG_SENSORS", flush=True)
for n in (b"SENS_EN_IMU", b"SENS_EN_MAG", b"SENS_EN_BARO"):
    set_param(n, 1, timeout=2)

t0 = time.time()
conn.mav.command_long_send(TARGET[0], TARGET[1], c.MAV_CMD_DO_SET_MODE,
                           0, c.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 6.0, 0, 0, 0, 0, 0)
end = time.time() + 8
got_ack = None
while time.time() < end:
    m = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=1.5)
    if m is not None and m.command == c.MAV_CMD_DO_SET_MODE:
        got_ack = m.result
        break
print("MODE_ACK=%s (t=%dms)" % (got_ack, (time.time()-t0)*1000), flush=True)

t0 = time.time()
conn.mav.command_long_send(TARGET[0], TARGET[1], c.MAV_CMD_COMPONENT_ARM_DISARM,
                           0, 1.0, 21196.0, 0, 0, 0, 0, 0)
end = time.time() + 25
n_ack = 0
while time.time() < end:
    m = conn.recv_match(type=["COMMAND_ACK", "STATUSTEXT", "EXTENDED_SYS_STATE",
                              "HEARTBEAT", "ESTIMATOR_STATUS", "GPS_RAW_INT",
                              "SYS_STATUS"], blocking=True, timeout=2)
    if m is None:
        continue
    t = m.get_type()
    if t == "COMMAND_ACK":
        n_ack += 1
        print("ACK(%d) cmd=%d result=%d" % (n_ack, m.command, m.result), flush=True)
    elif t == "STATUSTEXT":
        print("PX4(sev%d): %s" % (m.severity, m.text), flush=True)
    elif t == "EXTENDED_SYS_STATE":
        print("EXT landed=%d armed=%d" % (m.landed_state, m.in_air_motors_armed), flush=True)
    elif t == "HEARTBEAT":
        am = (m.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED) and 1 or 0
        print("HB armed=%d mode=0x%x" % (am, m.base_mode), flush=True)
        if am == 1:
            break
    elif t == "ESTIMATOR_STATUS":
        print("EST flags=0x%x vel=%d ph=%d pv=%d yaw=%d" %
              (m.flags, m.velocity_ratio, m.pos_horiz_ratio, m.pos_vert_ratio, m.yaw_comp_ratio), flush=True)
    elif t == "GPS_RAW_INT":
        print("GPS fixtype=%d sats=%d" % (m.fix_type, m.satellites_visible), flush=True)
    elif t == "SYS_STATUS":
        print("SYS sensors_health=0x%x" % m.onboard_control_sensors_health, flush=True)

_heartbeat_running = False
print("DONE (arm tried after %fs)" % (time.time()-t0), flush=True)