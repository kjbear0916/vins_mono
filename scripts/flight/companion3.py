#!/usr/bin/env python3
"""Persistent VINS companion3 -- the one that must run from second-0 of a
FRESH sim boot, on the ONBOARD link.

Dopes proven on the wire (wire60.pcap):
  - PX4 sends BOTH links to 127.0.0.1 (loopback-only) -- bind address was a
    red herring. The REAL mechanism is single-listener socket competition on
    14540; the provably-working raw monitor bound 0.0.0.0:14540 with reuseport
    and RECEIVED full-rate, while companion (0.0.0.0, no reuseport flag at
    socket level via pymavlink) starved. So: pymavlink udpin WITHOUT reuseaddr
    + NO other listener = exactly the conditions that worked.
  - typemask must be 2552 (this dialect: X/Y/Z set, V+VZ+AF*A*+yaw-rate
    ignored, yaw NOT ignored) -- computed from available constants, no
    TAKEOFF/AFX/AFY/AFZ in this dialect.

Deliverables: persistent heartbeat from second 0, continuous OFFBOARD
position setpoints, relax SYS_HAS_*/COM_ARM_*, OFFBOARD mode, arm attempts,
STATUSTEXT + COMMAND_ACK -> written to /tmp/companion3_out.log AND stdout.
"""
import threading
import time
from collections import OrderedDict

import pymavlink.dialects.v20.common as c
from pymavlink import mavutil

SRC_PORT = 14540
BIND = "0.0.0.0"
TARGET = (1, 1)
# this dialect: validate names
for n in ("MAV_TYPE_ONBOARD_CONTROLLER", "POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE"):
    assert hasattr(c, n), "missing dialect constant: " + n

SYSID_SRC = 255

_running = True


def hb_thread(conn):
    while _running:
        try:
            conn.mav.heartbeat_send(c.MAV_TYPE_ONBOARD_CONTROLLER,
                                    c.MAV_AUTOPILOT_INVALID, 0, 0, c.MAV_STATE_ACTIVE)
        except Exception:
            pass
        time.sleep(0.6)


def sp_thread(conn):
    while _running:
        try:
            conn.mav.set_position_target_local_ned_send(
                0, TARGET[0], TARGET[1],
                c.MAV_FRAME_LOCAL_NED, 2552,
                0.0, 0.0, -1.5,
                0.0, 0.0, 0.0,
                0.0, 0.0, 0.0,
                0.0, 0.0)
        except Exception:
            pass
        time.sleep(0.05)


def set_param(conn, name, val, ptype=c.MAV_PARAM_TYPE_INT32):
    conn.mav.param_set_send(TARGET[0], TARGET[1], name, float(val), ptype)
    conn.mav.param_request_read_send(TARGET[0], TARGET[1], name, -1)
    pv = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
    print("  PARAM %-14s -> %s" % (name.decode(), (pv.param_value if pv else "NO_READBACK")), flush=True)


def arm(conn, pw, timeout=10):
    conn.mav.command_long_send(TARGET[0], TARGET[1], c.MAV_CMD_COMPONENT_ARM_DISARM,
                               0, pw, 21196.0, 0, 0, 0, 0, 0)
    end = time.time() + timeout
    result = None
    while time.time() < end:
        m = conn.recv_match(type=["COMMAND_ACK", "STATUSTEXT"], blocking=True, timeout=3)
        if m is None:
            continue
        if m.get_type() == "STATUSTEXT":
            print("  PX4-%d: %s" % (m.severity, m.text), flush=True)
        else:
            result = m.result
            print("  ACK %d" % result, flush=True)
            break
    return result


def main():
    conn = mavutil.mavlink_connection("udpin:%s:%d" % (BIND, SRC_PORT))
    conn.mav.srcSystem = SYSID_SRC
    conn.mav.srcComponent = 0

    th_h = threading.Thread(target=hb_thread, args=(conn,), daemon=True)
    th_s = threading.Thread(target=sp_thread, args=(conn,), daemon=True)
    th_h.start()
    th_s.start()

    print("WAIT_HB", flush=True)
    hb = None
    for _ in range(8):
        hb = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=4)
        if hb is not None:
            break
    if hb is None:
        print("FINAL NO_HB", flush=True)
        return
    print("HB base=0x%x cmp=%d" % (hb.base_mode, hb.get_srcComponent() or 0), flush=True)

    for name in (b"SYS_HAS_MAG", b"SYS_HAS_BARO", b"SYS_HAS_GPS"):
        set_param(conn, name, 1)
        time.sleep(0.4)
    for name in (b"COM_ARM_ARSPD_EN", b"COM_ARM_EKF_POS", b"COM_ARM_EKF_VEL",
                 b"COM_ARM_EKF_HGT", b"COM_ARM_EKF_YAW", b"COM_ARM_WO_GPS",
                 b"COM_ARM_AUTH_REQ"):
        set_param(conn, name, 0)
        time.sleep(0.3)

    print("OFFBOARD", flush=True)
    conn.set_mode_apm(c.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, c.PX4_CUSTOM_MAIN_MODE_OFFBOARD)
    time.sleep(1.5)

    res = None
    for attempt in range(1, 8):
        res = arm(conn, 1.0, 14)
        if res == c.MAV_RESULT_ACCEPTED:
            print("FINAL ARMED_OK attempt=%d" % attempt, flush=True)
            break
        time.sleep(1.0)
    else:
        print("FINAL ARMED=%s" % (res,), flush=True)

    time.sleep(8)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
