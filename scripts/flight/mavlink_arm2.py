#!/usr/bin/env python3
"""Offboard+arm helper, single-socket bidirectional UDP (udpout).

Tries Onboard link (->14580) then GCS link (->18570). px4 replies to the
source address, so one udpout socket carries both directions.
"""
import sys
import time
from pymavlink import mavutil
from pymavlink.dialects.v20 import common as c

TARGET_SYS = 1
TARGET_COMP = 1


def make_conn(port):
    conn = mavutil.mavlink_connection("udpout:127.0.0.1:%d" % port)
    conn.mav.srcSystem = 255
    conn.mav.srcComponent = 0
    return conn


def recv_hb(conn, timeout=9):
    t0 = time.time()
    while time.time() - t0 < timeout:
        m = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=1.5)
        if m is not None and m.get_srcSystem() == 1:
            return m
    return None


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
    conn = None
    got = None
    errs = []
    for port, name in ((14580, "onboard->14580"), (18570, "gcs->18570")):
        try:
            print("TRY %s" % name, flush=True)
            conn = make_conn(port)
            got = recv_hb(conn)
            if got is not None:
                print("HB on %s" % name, flush=True)
                break
            errs.append("no hb on %s" % name)
            conn = None
        except Exception as e:
            errs.append("%s: %s" % (name, e))
    if got is None:
        print("NO_HEARTBEAT [%s]" % "; ".join(errs), flush=True)
        return 2
    print("FCU_KNOWN sysid=%d armed=%d mode=0x%x" % (
        got.get_srcSystem(),
        (got.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED) and 1 or 0,
        got.base_mode), flush=True)

    if not only_arm:
        r = send_sys_cmd(
            conn, c.MAV_CMD_DO_SET_MODE,
            c.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            6.0, 0, 0, 0, 0, 0)  # 6.0 = OFFBOARD
        print("SET_MODE_OFFBOARD_ACK=%s" % r, flush=True)

    for name, ptype in (
        (b"SYS_HAS_MAG", c.MAV_PARAM_TYPE_INT32),
        (b"SYS_HAS_BARO", c.MAV_PARAM_TYPE_INT32),
        (b"SYS_HAS_GPS", c.MAV_PARAM_TYPE_INT32),
        (b"COM_ARM_WO_GPS", c.MAV_PARAM_TYPE_INT32),
    ):
        conn.mav.param_request_read_send(TARGET_SYS, TARGET_COMP, name, -1)
        pv = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
        print("PARAM %s = %r" % (name.decode(), pv.param_value if pv else None), flush=True)

    for name, val, ptype in (
        (b"COM_ARM_WO_GPS", 1, c.MAV_PARAM_TYPE_INT32),
        (b"COM_ARM_ARSPD_EN", 0, c.MAV_PARAM_TYPE_INT32),
        (b"COM_ARM_EKF_POS", 0, c.MAV_PARAM_TYPE_INT32),
        (b"COM_ARM_EKF_VEL", 0, c.MAV_PARAM_TYPE_INT32),
        (b"COM_ARM_EKF_HGT", 0, c.MAV_PARAM_TYPE_INT32),
        (b"COM_ARM_EKF_YAW", 0, c.MAV_PARAM_TYPE_INT32),
    ):
        conn.mav.param_set_send(TARGET_SYS, TARGET_COMP, name, val, ptype)
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
            m = conn.recv_match(type=["STATUSTEXT", "EVENT", "EXTENDED_SYS_STATE"],
                                blocking=False, timeout=0.2)
            if m is not None:
                if m.get_type() == "STATUSTEXT":
                    print("  PX4_TEXT: %s" % m.text, flush=True)
                elif m.get_type() == "EVENT":
                    print("  PX4_EVENT: id=%d a=%r" % (m.id, m.arguments), flush=True)
                else:
                    print("  EXT_SYS: vtol=%d landed=%d inair_mp=%d" %
                          (m.vtol_state, m.landed_state, m.in_air_motors_armed), flush=True)
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