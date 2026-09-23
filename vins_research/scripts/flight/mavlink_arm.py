#!/usr/bin/env python3
"""Raw-MAVLink offboard+arm helper for PX4 SITL.

Connects via the GCS MAVLink link (PX4 local 18570, remote 14550).
Flow:
  1. Wait for heartbeat from FCU
  2. Set OFFBOARD mode
  3. Read default SYS_HAS_* (don't touch - let EKF use baro/mag)
  4. Relax non-sensor arming gates
  5. Arm attempt
"""
import sys
import time
from pymavlink import mavutil
from pymavlink.dialects.v20 import common as c

TARGET_SYS = 1
TARGET_COMP = 1


def send_sys_cmd(conn, mav_cmd, *params):
    conn.mav.command_long_send(TARGET_SYS, TARGET_COMP, mav_cmd, 0, *params)
    deadline = time.time() + 6
    while time.time() < deadline:
        msg = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=2)
        if msg is None:
            continue
        if msg.command == mav_cmd:
            return msg.result
    return None


def main():
    only_arm = "--only-arm" in sys.argv
    # GCS link: PX4 listens 18570, sends to 14550. We bind 14550.
    conn = mavutil.mavlink_connection("udpin:127.0.0.1:14550")
    conn.mav.srcSystem = 255
    conn.mav.srcComponent = 0

    print("WAIT_HEARTBEAT (14550)", flush=True)
    got = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=15)
    if got is None:
        print("NO_HEARTBEAT on 14550", flush=True)
        return 2
    print("FCU_KNOWN sysid=%d armed=%d mode=0x%x" % (
        got.get_srcSystem(),
        (got.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED) and 1 or 0,
        got.base_mode), flush=True)

    if not only_arm:
        r = send_sys_cmd(
            conn, c.MAV_CMD_DO_SET_MODE,
            c.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            6.0, 0, 0, 0, 0, 0)
        print("SET_MODE_OFFBOARD_ACK=%s" % r, flush=True)

    # Read default sensor params (DON'T set to 0 - EKF needs them!)
    for name in (b"SYS_HAS_MAG", b"SYS_HAS_BARO", b"SYS_HAS_GPS"):
        conn.mav.param_request_read_send(TARGET_SYS, TARGET_COMP, name, -1)
        pv = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
        print("PARAM %s = %r" % (name.decode(), pv.param_value if pv else None), flush=True)

    # Relax non-sensor arming gates
    for name, val in (
        (b"COM_ARM_WO_GPS", 1),
        (b"COM_ARM_ARSPD_EN", 0),
        (b"COM_ARM_EKF_POS", 0),
        (b"COM_ARM_EKF_VEL", 0),
        (b"COM_ARM_EKF_HGT", 0),
        (b"COM_ARM_EKF_YAW", 0),
    ):
        conn.mav.param_set_send(TARGET_SYS, TARGET_COMP, name, float(val), c.MAV_PARAM_TYPE_INT32)
        time.sleep(0.6)
        conn.mav.param_request_read_send(TARGET_SYS, TARGET_COMP, name, -1)
        pv = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
        if pv is not None:
            print("SET %s = %r" % (name.decode(), pv.param_value), flush=True)
    time.sleep(1.0)

    result = None
    for attempt in range(1, 7):
        result = send_sys_cmd(
            conn, c.MAV_CMD_COMPONENT_ARM_DISARM, 1.0, 21196.0, 0, 0, 0, 0, 0)
        print("ARM_ATTEMPT%d=%s" % (attempt, result), flush=True)
        if result == c.MAV_RESULT_ACCEPTED:
            break
        deadline = time.time() + 2.0
        while time.time() < deadline:
            m = conn.recv_match(type=["STATUSTEXT", "EXTENDED_SYS_STATE"],
                                blocking=False, timeout=0.2)
            if m is not None:
                if m.get_type() == "STATUSTEXT":
                    print("  PX4: %s" % m.text, flush=True)
                else:
                    print("  EXT: landed=%d armed=%d" % (m.landed_state, m.in_air_motors_armed), flush=True)
        time.sleep(0.5)

    armed = None
    deadline = time.time() + 5
    while time.time() < deadline:
        hb = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if hb is not None:
            armed = (hb.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED) and 1 or 0
            if armed == 1:
                break
    print("FINAL_ARMED=%s" % armed, flush=True)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())