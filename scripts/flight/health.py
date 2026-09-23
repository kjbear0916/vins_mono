#!/usr/bin/env python3
"""Health check for vins_research sim: procs, live params.bson SYS_HAS_*/COM_ARM_*, UDP binders."""
import os, re, subprocess, struct

def sh(cmd, t=20):
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=t)
        return r.stdout + r.stderr
    except Exception as e:
        return "ERR %s" % e

print("== PROCS ==")
print(sh("ps -eo pid,etimes,cmd | grep -E 'gzserver|/bin/px4|rosmaster|roscore|roscome|sitl_run' | grep -v grep"))
print("\n== UDP 14540/14550/14580/18570 ==")
print(sh("ss -ulnp | grep -E ':14540|:14550|:14580|:18570' || echo '(none bound)'"))

print("\n== LIVE parameters.bson (SYS_HAS_* / COM_ARM_*) ==")
p = "/root/PX4-Autopilot/build/px4_sitl_default/rootfs/parameters.bson"
if os.path.exists(p):
    data = open(p, "rb").read()
    print("size=%d" % len(data))
    # scan for the relevant param names as bytes
    for name in (b"SYS_HAS_MAG", b"SYS_HAS_BARO", b"SYS_HAS_GPS",
                 b"COM_ARM_ARSPD_EN", b"COM_ARM_EKF_POS", b"COM_ARM_EKF_VEL",
                 b"COM_ARM_EKF_HGT", b"COM_ARM_EKF_YAW", b"COM_ARM_WO_GPS"):
        idx = data.find(name)
        if idx >= 0:
            print("  found %-18s @%d  ctx=%s" % (name.decode(), idx, data[max(0,idx-8):idx+len(name)+8].hex(" ")))
        else:
            print("  %-18s NOT in file" % name.decode())
else:
    print("  missing: %s" % p)
