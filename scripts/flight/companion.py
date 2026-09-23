#!/usr/bin/env python3
"""Persistent companion on the onboard link (PX4 local 14580, remote 14540).

Sends GCS-like heartbeat + continuous OFFBOARD setpoints, armed attempts,
keeps the link alive. Models exactly what the real flight script will do.
"""
import threading
import time
from pymavlink import mavutil
from pymavlink.dialects.v20 import common as c

LINK_SRC = 14540
conn = mavutil.mavlink_connection("udpin:127.0.0.1:%d" % LINK_SRC)
conn.mav.srcSystem = 255
conn.mav.srcComponent = 0

stop = False

def hb_loop():
    while not stop:
        conn.mav.heartbeat_send(c.MAV_TYPE_GCS, c.MAV_AUTOPILOT_INVALID,
                                c.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 0, c.MAV_STATE_ACTIVE)
        time.sleep(1.0)

def sp_loop():
    while not stop:
        conn.mav.set_position_target_local_ned_send(
            0, 1, 1, c.MAV_FRAME_LOCAL_NED, c.POSITION_TARGET_TYPEMASK_TAKEOFF,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        time.sleep(0.02)

threading.Thread(target=hb_loop, daemon=True).start()

print("WAIT_HB onboard", flush=True)
hb = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=20)
if hb is None:
    print("NO_HB onboard", flush=True)
    stop = True
    raise SystemExit(2)
print("HB armed=%d mode=0x%x" % ((hb.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED) and 1 or 0,
                                 hb.base_mode), flush=True)

# reset sensors (stale persisted zeros)
for name, val in ((b"SYS_HAS_MAG", 1), (b"SYS_HAS_BARO", 1), (b"SYS_HAS_GPS", 1)):
    conn.mav.param_set_send(1, 1, name, float(val), c.MAV_PARAM_TYPE_INT32)
    conn.mav.param_request_read_send(1, 1, name, -1)
    pv = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
    print("P %s=%r" % (name.decode(), pv.param_value if pv else None), flush=True)
    time.sleep(0.5)

# OFFBOARD + hold (typemask takeoff = ignore everything but provide the mode)
conn.mav.command_long_send(1, 1, c.MAV_CMD_DO_SET_MODE, 0,
                           c.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 6.0, 0, 0, 0, 0, 0)
threading.Thread(target=sp_loop, daemon=True).start()

t_end = time.time() + 40
armed = 0
att_done = 0
while time.time() < t_end:
    m = conn.recv_match(type=["COMMAND_ACK", "STATUSTEXT", "EXTENDED_SYS_STATE",
                              "HEARTBEAT", "SYS_STATUS", "GPS_RAW_INT"], blocking=True, timeout=2)
    if m is None:
        continue
    t = m.get_type()
    if t == "HEARTBEAT":
        armed = (m.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED) and 1 or 0
        if armed == 1:
            print("=== ARMED ===", flush=True)
    elif t == "COMMAND_ACK":
        print("ACK cmd=%d result=%d" % (m.command, m.result), flush=True)
        if m.command == c.MAV_CMD_COMPONENT_ARM_DISARM and m.result == c.MAV_RESULT_ACCEPTED and not att_done:
            att_done = 1
    elif t == "STATUSTEXT":
        print("PX4(sev%d): %s" % (m.severity, m.text), flush=True)
    elif t == "EXTENDED_SYS_STATE":
        print("EXT landed=%d armed=%d" % (m.landed_state, m.in_air_motors_armed), flush=True)
    elif t == "SYS_STATUS":
        print("SYS health=0x%x" % m.onboard_control_sensors_health, flush=True)
    elif t == "GPS_RAW_INT":
        print("GPS fixtype=%d sats=%d" % (m.fix_type, m.satellites_visible), flush=True)

    # periodic arm attempts if not armed yet
    if not armed and time.time() % 5 < 0.01:
        conn.mav.command_long_send(1, 1, c.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                                   1.0, 21196.0, 0, 0, 0, 0, 0)
        print("ARM-ATTEMPT", flush=True)

stop = True
print("FINAL armed=%d" % armed, flush=True)