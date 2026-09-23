#!/usr/bin/env python3
"""Persistent companion on the ONBOARD link (PX4 local 14540, remote 14580).
Keeps heartbeats + OFFBOARD setpoints flowing continuously (as the real
VINS companion will), fixes sensor params, and arms. Logs STATUSTEXT/ACKs."""
import sys
import threading
import time
from pymavlink import mavutil
from pymavlink.dialects.v20 import common as c

TARGET = (1, 1)
SRC_PORT = 14540   # onboard/companion link local port (bind 0.0.0.0)
conn = mavutil.mavlink_connection("udpin:0.0.0.0:%d" % SRC_PORT)
conn.mav.srcSystem = 255
conn.mav.srcComponent = 0
_running = True


def hb_loop():
    while _running:
        conn.mav.heartbeat_send(c.MAV_TYPE_GCS, c.MAV_AUTOPILOT_INVALID,
                                c.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 0, c.MAV_STATE_ACTIVE)
        time.sleep(1.0)


def sp_loop():
    while _running:
        # velocity setpoint (vx=1 m/s) as offboard authority, sent continuously
        conn.mav.set_position_target_local_ned_send(
            0, 1, 1, c.MAV_FRAME_LOCAL_NED, c.POSITION_TARGET_TYPEMASK_TAKEOFF,  # ignored mask
            0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        time.sleep(0.04)


threading.Thread(target=hb_loop, daemon=True).start()
threading.Thread(target=sp_loop, daemon=True).start()

print("WAIT_HB", flush=True)
hb = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=15)
if hb is None:
    print("NO_HB", flush=True)
    raise SystemExit(2)
print("HB_KNOWN sysid=%d armed=%d" % (
    hb.get_srcSystem(),
    (hb.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED) and 1 or 0), flush=True)

t0 = time.time()


def xchg(t, timeout=4, **kw):
    return conn.recv_match(type=t, blocking=False, timeout=timeout, **kw)


def send_cmd(cmd, *params):
    conn.mav.command_long_send(TARGET[0], TARGET[1], cmd, 0, *params)
    ack = None
    end = time.time() + 6
    while time.time() < end:
        m = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=2)
        if m is not None and m.command == cmd:
            ack = m.result
            break
    return ack


def get_param(name):
    conn.mav.param_request_read_send(TARGET[0], TARGET[1], name, -1)
    pv = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
    return pv.param_value if pv else None


def set_param(name, val):
    conn.mav.param_set_send(TARGET[0], TARGET[1], name, float(val), c.MAV_PARAM_TYPE_INT32)
    time.sleep(0.4)
    return get_param(name)


print("PARAM_READ", flush=True)
for name in (b"SYS_HAS_MAG", b"SYS_HAS_BARO", b"SYS_HAS_GPS"):
    print("  %s = %r" % (name.decode(), get_param(name)), flush=True)
    time.sleep(0.2)

# Reset to defaults (they were forced to 0 by earlier experiments)
for n, v in ((b"SYS_HAS_MAG", 1), (b"SYS_HAS_BARO", 1), (b"SYS_HAS_GPS", 1)):
    print("  SET %s->%d = ...%r" % (n.decode(), v, set_param(n, v)), flush=True)

# OFFBOARD mode (custom mode 6 = offboard in 1.14)
send_cmd(c.MAV_CMD_DO_SET_MODE, c.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 6.0, 0, 0, 0, 0, 0)
print("MODE_SENT", flush=True)

# relax non-sensor gates (these ensure we arm without position/GCS requirements)
for n, v in ((b"COM_ARM_AUTH_REQ", 0), (b"COM_ARM_ARSPD_EN", 0),
             (b"COM_ARM_ODOM", 0), (b"COM_ARM_MIS_ALND", 0)):
    set_param(n, v)

print("AUTO_LOOP", flush=True)
armed = False
last_arm = time.time()
end = time.time() + 60
while time.time() < end:
    m = conn.recv_match(type=["STATUSTEXT", "EXTENDED_SYS_STATE",
                              "EYE_ESTIMATOR_STATUS", "GPS_RAW_INT",
                              "SYS_STATUS"], blocking=True, timeout=2)
    if m is None:
        continue
    t = m.get_type()
    if t == "STATUSTEXT":
        print("PY4(sev%d): %s" % (m.severity, m.text), flush=True)
    elif t == "GPS_RAW_INT":
        print("GPS f=%d s=%d" % (m.fix_type, m.satellites_visible), flush=True)
    elif t == "SYS_STATUS":
        print("SYS on_ctl_sensors_health=0x%x" % (m.onboard_control_sensors_health), flush=True)
    elif t == "EXTENDED_SYS_STATE":
        if m.in_air_motors_armed:
            print("=== ARMED ===", flush=True)
            armed = True
            break
    if time.time() - last_arm > 4.0:
        r = send_cmd(c.MAV_CMD_COMPONENT_ARM_DISARM, 1.0, 21196.0, 0, 0, 0, 0, 0)
        print("ARMATTEMPT result=%s" % r, flush=True)
        last_arm = time.time()

print("FINAL armed=%s" % armed, flush=True)
