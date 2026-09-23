#!/usr/bin/env python3
"""Reset SYS_HAS_* to 1, then arm and capture the denial reason STATUSTEXT."""
import time
from pymavlink import mavutil
from pymavlink.dialects.v20 import common as c

TARGET = (1, 1)

def set_param(conn, name, val):
    conn.mav.param_set_send(TARGET[0], TARGET[1], name, float(val), c.MAV_PARAM_TYPE_INT32)
    conn.mav.param_request_read_send(TARGET[0], TARGET[1], name, -1)
    pv = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
    return pv.param_value if pv else None

conn = mavutil.mavlink_connection("udpin:127.0.0.1:14550")
conn.mav.srcSystem = 255
conn.mav.srcComponent = 0

hb = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=15)
print("HB sysid=%d armed=%d mode=0x%x" % (hb.get_srcSystem(),
      (hb.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED) and 1 or 0, hb.base_mode), flush=True)

for name, val in ((b"SYS_HAS_MAG", 1), (b"SYS_HAS_BARO", 1), (b"SYS_HAS_GPS", 1)):
    r = set_param(conn, name, val)
    print("reset %s -> %r" % (name.decode(), r), flush=True)
    time.sleep(0.4)

# Enter OFFBOARD
conn.mav.command_long_send(TARGET[0], TARGET[1], c.MAV_CMD_DO_SET_MODE,
                           0, c.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 6.0, 0, 0, 0, 0, 0)
ack = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=6)
print("MODE_ACK=%s" % (ack.result if ack else None), flush=True)

# Arm and capture everything
conn.mav.command_long_send(TARGET[0], TARGET[1], c.MAV_CMD_COMPONENT_ARM_DISARM,
                           0, 1.0, 21196.0, 0, 0, 0, 0, 0)
end = time.time() + 20
while time.time() < end:
    m = conn.recv_match(type=["COMMAND_ACK", "STATUSTEXT", "EXTENDED_SYS_STATE",
                              "GPS_RAW_INT", "LOCAL_POSITION_NED", "GLOBAL_POSITION_INT",
                              "SYS_STATUS", "ESTIMATOR_STATUS", "HEARTBEAT"],
                        blocking=True, timeout=2)
    if m is None:
        continue
    t = m.get_type()
    if t == "COMMAND_ACK":
        print("ACK cmd=%d result=%d" % (m.command, m.result), flush=True)
    elif t == "STATUSTEXT":
        print("PX4_TEXT(sev%d): %s" % (m.severity, m.text), flush=True)
    elif t == "EXTENDED_SYS_STATE":
        print("EXT landed=%d armed=%d" % (m.landed_state, m.in_air_motors_armed), flush=True)
    elif t == "SYS_STATUS":
        print("SYS onboard_sensors_health=0x%x vol=%d mV" % (m.onboard_control_sensors_health, m.voltage_battery), flush=True)
    elif t == "HEARTBEAT":
        print("HB armed=%d mode=0x%x" % ((m.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED) and 1 or 0, m.base_mode), flush=True)
    elif t == "GPS_RAW_INT":
        print("GPS fixtype=%d sats=%d" % (m.fix_type, m.satellites_visible), flush=True)
    elif t == "ESTIMATOR_STATUS":
        print("EST flags=0x%x vel_ratio=%d pos_horiz_ratio=%d pos_vert_ratio=%d yaw_ratio=%d" %
              (m.flags, m.velocity_ratio, m.pos_horiz_ratio, m.pos_vert_ratio, m.yaw_comp_ratio), flush=True)
    elif t == "LOCAL_POSITION_NED":
        pass
print("DONE", flush=True)