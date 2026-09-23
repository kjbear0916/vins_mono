#!/usr/bin/env python3
import pymavlink.mavutil as mavutil
import pymavlink.dialects.v20.ardupilotmega as ac
import time

conn = mavutil.mavlink_connection("udpin:127.0.0.1:14540", dialect="ardupilotmega")
conn.mav.heartbeat_send(ac.MAV_TYPE_GCS, ac.MAV_AUTOPILOT_INVALID, 0, 0, 0)
if conn.recv_match(type="HEARTBEAT", blocking=True, timeout=15) is None:
    print("NO_HB")
    raise SystemExit(1)

for name in (b"COM_ARM_EKF_POS", b"COM_ARM_EKF_VEL", b"COM_ARM_EKF_HGT",
             b"COM_ARM_EKF_YAW", b"COM_ARM_WO_GPS", b"SYS_HAS_MAG",
             b"SYS_HAS_BARO", b"SYS_HAS_GPS", b"COM_ARM_MIS_REQ"):
    conn.mav.param_request_read_send(1, 1, name, -1)
    got = None
    for _ in range(3):
        m = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=2)
        if m is None:
            break
        if m.param_id == name:
            got = m.param_value
            break
        time.sleep(0.1)
    print("%s = %s" % (name.decode(), got), flush=True)

conn.mav.command_long_send(1, 1, ac.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                           1.0, 21196.0, 0, 0, 0, 0, 0)
for _ in range(4):
    m = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=2)
    if m is not None:
        print("ACK res=%d" % m.result, flush=True)
        break