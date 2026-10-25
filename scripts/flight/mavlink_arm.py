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
import struct
from pymavlink import mavutil
from pymavlink.dialects.v20 import common as c

TARGET_SYS = 1
TARGET_COMP = 1


def param_wire_value(value, param_type):
    """Encode integer MAVLink params as the required float32 bit payload."""
    if param_type == c.MAV_PARAM_TYPE_INT32:
        return struct.unpack("<f", struct.pack("<i", int(value)))[0]
    return float(value)


def param_read_value(message):
    """Decode PARAM_VALUE using the type supplied by PX4."""
    if message is None:
        return None
    if message.param_type == c.MAV_PARAM_TYPE_INT32:
        return struct.unpack("<i", struct.pack("<f", message.param_value))[0]
    return message.param_value


def read_param(conn, name, timeout=3):
    """Read one named parameter, ignoring delayed replies for other params."""
    conn.mav.param_request_read_send(TARGET_SYS, TARGET_COMP, name, -1)
    deadline = time.time() + timeout
    expected = name.decode()
    while time.time() < deadline:
        message = conn.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if message is not None and message.param_id.rstrip("\x00") == expected:
            return message
    return None


def is_fcu(message):
    return (message is not None and message.get_srcSystem() == TARGET_SYS
            and message.get_srcComponent() == TARGET_COMP)


def send_sys_cmd(conn, mav_cmd, *params):
    conn.mav.command_long_send(TARGET_SYS, TARGET_COMP, mav_cmd, 0, *params)
    deadline = time.time() + 6
    while time.time() < deadline:
        msg = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=2)
        if msg is None:
            continue
        if is_fcu(msg) and msg.command == mav_cmd:
            return msg.result
    return None


def main():
    only_arm = "--only-arm" in sys.argv
    # GCS link: PX4 listens 18570, sends to 14550. We bind 14550.
    conn = mavutil.mavlink_connection("udpin:127.0.0.1:14550")
    conn.mav.srcSystem = 255
    conn.mav.srcComponent = 0

    print("WAIT_HEARTBEAT (14550)", flush=True)
    got = None
    heartbeat_deadline = time.time() + 15
    while time.time() < heartbeat_deadline:
        candidate = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if is_fcu(candidate):
            got = candidate
            break
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
        pv = read_param(conn, name)
        print("PARAM %s = %r" % (name.decode(), param_read_value(pv)), flush=True)

    # PX4 treats these as *maximum* permitted innovation ratios.  Zero does
    # not disable a check: it rejects every non-zero (normal) innovation.
    # Keep the documented PX4 defaults instead.
    for name, val, ptype in (
        (b"COM_ARM_WO_GPS", 1, c.MAV_PARAM_TYPE_INT32),
        (b"COM_ARM_EKF_POS", 0.5, c.MAV_PARAM_TYPE_REAL32),
        (b"COM_ARM_EKF_VEL", 0.5, c.MAV_PARAM_TYPE_REAL32),
        (b"COM_ARM_EKF_HGT", 1.0, c.MAV_PARAM_TYPE_REAL32),
        (b"COM_ARM_EKF_YAW", 0.5, c.MAV_PARAM_TYPE_REAL32),
    ):
        conn.mav.param_set_send(TARGET_SYS, TARGET_COMP, name,
                                param_wire_value(val, ptype), ptype)
        time.sleep(0.6)
        pv = read_param(conn, name)
        if pv is not None:
            print("SET %s = %r" % (name.decode(), param_read_value(pv)), flush=True)
    time.sleep(1.0)

    result = None
    got_armed = False
    for attempt in range(1, 10):
        result = send_sys_cmd(
            conn, c.MAV_CMD_COMPONENT_ARM_DISARM, 1.0, 21196.0, 0, 0, 0, 0, 0)
        print("ARM_ATTEMPT%d=%s" % (attempt, result), flush=True)
        if result == c.MAV_RESULT_ACCEPTED:
            # ACK means the command was accepted, not that the vehicle is
            # armed. The heartbeat check below is the source of truth.
            break
        deadline = time.time() + 4.0
        while time.time() < deadline:
            m = conn.recv_match(type=["STATUSTEXT", "EXTENDED_SYS_STATE"],
                                blocking=False, timeout=0.2)
            if m is not None:
                if m.get_type() == "STATUSTEXT":
                    print("  PX4: %s" % m.text, flush=True)
                else:
                    motor = getattr(m, "in_air_motors_armed", getattr(m, "armed", "?"))
                    print("  EXT: landed=%d armed=%s" % (m.landed_state, motor), flush=True)
            hb = conn.recv_match(type="HEARTBEAT", blocking=False, timeout=0.2)
            if is_fcu(hb) and (hb.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED):
                got_armed = True
                break
        if got_armed:
            break
        time.sleep(0.5)

    armed = None
    deadline = time.time() + 5
    while time.time() < deadline:
        hb = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if is_fcu(hb):
            armed = (hb.base_mode & c.MAV_MODE_FLAG_SAFETY_ARMED) and 1 or 0
            if armed == 1:
                break
    print("FINAL_ARMED=%s" % (1 if got_armed or armed == 1 else None), flush=True)
    print("DONE", flush=True)
    return 0 if (got_armed or armed == 1) else 1


if __name__ == "__main__":
    sys.exit(main())
