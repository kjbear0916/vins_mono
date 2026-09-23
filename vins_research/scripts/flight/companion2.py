#!/usr/bin/env python3
"""PERSISTENT companion — the actual VINS companion architecture.

After pcap64 proof:
  dst map  14580->127.0.0.1:14540 (onboard companion, WHERE WE BIND)
           18570->127.0.0.1:14550 (GCS)
  -> 0.0.0.0 is NOT required for reception. The '0.0.0.0 worked / 127.0.0.1 failed'
     was UDP-socket-delivery competition: the raw link monitor (bound 0.0.0.0:14550
     earlier) starved the companion (bound 127.0.0.1:14540) because PX4 only ever
     sends ONE copy per loopback packet. Exactly one listener must own the link.

  So: SINGLE listener on the onboard/home link, bound 0.0.0.0 (matches the monitor
  that provably streams), heartbeat + OFFBOARD setpoints from second 0, never stops
  (keeps `_wait_to_transmit`/`_received_messages` state -> link never collapses),
  relaxes arm gates, arms, then streams setpoints so we observe the true
  STATUSTEXT/ARM_ACK and finally the VINS trajectory.

PX4 onboard instance (px4-rc.mavlink, iris_fpv_cam instance 0):
  mavlink start -x -u $udp_offboard_port_local (14580) -m onboard -o 14540
  mavlink start -x -u $udp_gcs_port_local (18570) -m normal -o 14550
"""
import threading
import time

from pymavlink import mavutil
import pymavlink.dialects.v20.common as c

TARGET = (1, 1)
TYPEMASK_POS = 2552  # position-only local NED: V|A|yaw-rate ignore

MAVTYPE = c.MAV_TYPE_ONBOARD_CONTROLLER if hasattr(c, "MAV_TYPE_ONBOARD_CONTROLLER") else c.MAV_TYPE_GCS
_running = True


def set_param(conn, name, val, ptype=c.MAV_PARAM_TYPE_INT32):
    conn.mav.param_set_send(TARGET[0], TARGET[1], name, float(val), ptype)
    conn.mav.param_request_read_send(TARGET[0], TARGET[1], name, -1)
    pv = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=4)
    print("  PARAM %-14s -> %s" % (name.decode(), pv.param_value if pv else "NO_READBACK"), flush=True)
    return pv.param_value if pv else None


def arm(conn, pw, timeout=14):
    conn.mav.command_long_send(TARGET[0], TARGET[1], c.MAV_CMD_COMPONENT_ARM_DISARM,
                               0, pw, 21196.0, 0, 0, 0, 0, 0)
    end = time.time() + timeout
    result = None
    while time.time() < end:
        m = conn.recv_match(type=["COMMAND_ACK", "STATUSTEXT"], blocking=True, timeout=2)
        if m is None:
            continue
        if m.get_type() == "STATUSTEXT":
            print("  PX4[%d]: %s" % (m.severity, m.text), flush=True)
        elif m.command == c.MAV_CMD_COMPONENT_ARM_DISARM:
            result = m.result
            print("  ARM_ACK=%d" % result, flush=True)
            break
    return result


def hb_loop(conn):
    while _running:
        try:
            conn.mav.heartbeat_send(MAVTYPE, c.MAV_AUTOPILOT_INVALID, 0, 0, c.MAV_STATE_ACTIVE)
        except Exception:
            pass
        time.sleep(0.5)


def setpoint_loop(conn):
    z = -1.5
    while _running:
        try:
            conn.mav.set_position_target_local_ned_send(
                0, TARGET[0], TARGET[1], c.MAV_FRAME_LOCAL_NED, TYPEMASK_POS,
                0.0, 0.0, z, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        except Exception:
            pass
        time.sleep(0.03)


def main():
    conn = mavutil.mavlink_connection("udpin:0.0.0.0:%d" % 14540)
    conn.mav.srcSystem = 255
    conn.mav.srcComponent = 0

    th_hb = threading.Thread(target=hb_loop, args=(conn,), daemon=True)
    th_sp = threading.Thread(target=setpoint_loop, args=(conn,), daemon=True)
    th_hb.start()
    th_sp.start()

    hb = None
    for i in range(30):
        hb = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=4)
        if hb is not None:
            break
    if hb is None:
        print("FINAL NO_HB onboard", flush=True)
        return
    print("HB armed=%d mode=0x%x" % (
        hb.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED and 1 or 0, hb.base_mode), flush=True)
    time.sleep(0.5)

    print("= checks/sensors =", flush=True)
    for name, val, ptype in ((b"SYS_HAS_MAG", 1, c.MAV_PARAM_TYPE_INT32),
                             (b"SYS_HAS_BARO", 1, c.MAV_PARAM_TYPE_INT32),
                             (b"SYS_HAS_GPS", 1, c.MAV_PARAM_TYPE_INT32)):
        set_param(conn, name, val, ptype)
        time.sleep(0.45)

    print("= arm gates =", flush=True)
    for name, val in ((b"COM_ARM_ARSPD_EN", 0), (b"COM_ARM_EKF_POS", 0),
                      (b"COM_ARM_EKF_VEL", 0), (b"COM_ARM_EKF_HGT", 0),
                      (b"COM_ARM_EKF_YAW", 0), (b"COM_ARM_WO_GPS", 0),
                      (b"COM_ARM_AUTH_REQ", 0)):
        set_param(conn, name, val)
        time.sleep(0.35)

    print("= set OFFBOARD =", flush=True)
    conn.set_mode_apm(c.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, c.PX4_CUSTOM_MAIN_MODE_OFFBOARD)
    time.sleep(2)

    print("= arm attempts =", flush=True)
    res = None
    for attempt in range(1, 9):
        res = arm(conn, 1.0, timeout=14)
        if res == c.MAV_RESULT_ACCEPTED:
            print("FINAL ARMED_OK attempt=%d" % attempt, flush=True)
            break
        time.sleep(1.2)
    else:
        print("FINAL ARMED=%s" % (res,), flush=True)

    print("= post-arm setpoint 15s =", flush=True)
    time.sleep(15)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
