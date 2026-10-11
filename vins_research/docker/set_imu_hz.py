#!/usr/bin/env python3
"""set_imu_hz.py — set the HIGHRES_IMU onboard-stream rate in PX4 px4-rc.mavlink.

Item #12: mavros' /mavros/imu/data_raw rate is governed by the HIGHRES_IMU
stream on PX4's offboard/onboard MAVLink link. Rather than hand-editing the
deployed rc script (a manual edit that can silently persist into later runs),
the rate is chosen per-launch from IMU_HZ (default 50) and rewritten here.

Idempotent: any previous injection or stray HIGHRES_IMU line is removed first,
then the block is re-inserted right after the onboard offboard link start.
"""
import sys
import os

HZ = int(sys.argv[1]) if len(sys.argv) > 1 else 50

TARGETS = [
    "/root/PX4-Autopilot/build/px4_sitl_default/etc/init.d-posix/px4-rc.mavlink",
    "/root/PX4-Autopilot/ROMFS/px4fmu_common/init.d-posix/px4-rc.mavlink",
]
ANCHOR = "mavlink start -x -u $udp_offboard_port_local -r 4000000 -f -m onboard"
BLOCK = [
    "# --- IMU_HZ injection (managed by docker/set_imu_hz.py) ---",
    "mavlink stream -r %d -s HIGHRES_IMU -u $udp_offboard_port_local" % HZ,
    "# --- end IMU_HZ injection ---",
]


def process(lines):
    out = []
    skip = False
    for l in lines:
        if "IMU_HZ injection" in l:
            skip = not skip
            continue
        if "HIGHRES_IMU" in l or "#12" in l:
            continue
        if skip:
            continue
        out.append(l)
        if l.strip().startswith(ANCHOR):
            out.extend(BLOCK)
    return out


def main():
    changed = []
    for f in TARGETS:
        if not os.path.isfile(f):
            continue
        with open(f) as fh:
            lines = fh.read().splitlines()
        with open(f, "w") as fh:
            fh.write("\n".join(process(lines)) + "\n")
        changed.append(f)
    print("[set_imu_hz] IMU_HZ=%d applied to %d file(s)" % (HZ, len(changed)))
    if not changed:
        print("[set_imu_hz] WARNING: no px4-rc.mavlink target found")


if __name__ == "__main__":
    main()
