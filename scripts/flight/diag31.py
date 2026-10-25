#!/usr/bin/env python3
"""Diagnostic: pin pymavlink version/fields, find stale bson, list port binders.
Cheap, runs in ~2s."""
import os, re, subprocess, sys

print("PYTHON", sys.version.replace("\n", " "))
import pymavlink
from pymavlink.dialects.v20 import common as c
import pymavlink.dialects.v20.common as mod
f = os.path.abspath(mod.__file__)
print("PYMAVLINK", os.path.dirname(os.path.dirname(pymavlink.__file__)))
print("DIALECT", f)

src = open(f, encoding="utf-8", errors="replace").read()
masks = {}
for line in src.splitlines():
    m = re.match(r"\s*(POSITION_TARGET_TYPEMASK_[A-Z_]+)\s*=\s*(\d+)", line)
    if m:
        masks[m.group(1)] = int(m.group(2))
print("TYPEMASKS_COUNT", len(masks))
for k in sorted(masks):
    print("  ", k, "=", masks[k])

print("--- EXTENDED_SYS_STATE class ---")
ii = src.find("class MAVLink_extended_sys_state_message")
seg = src[ii:ii + 1400] if ii >= 0 else "(class not found)"
print(seg.strip()[:1200])

print("--- SYS_HAS / COM_ARM defaults present? ---")
for name in ("SYS_HAS_MAG", "SYS_HAS_BARO", "SYS_HAS_GPS",
             "COM_ARM_ARSPD_EN", "COM_ARM_EKF_POS", "COM_ARM_EKF_VEL",
             "COM_ARM_EKF_HGT", "COM_ARM_EKF_YAW", "COM_ARM_WO_GPS"):
    print("  ", name, name in src)

print("--- parameters.bson anywhere ---")
try:
    out = subprocess.run(["find", "/", "-name", "parameters.bson*"],
                         capture_output=True, text=True, timeout=30)
    print(out.stdout or "(none)")
except Exception as e:
    print("find err", e)

print("--- python procs ---")
try:
    out = subprocess.run(["bash", "-c",
                          "ps -eo pid,etimes,cmd | grep -E 'python|raw_14|companion|arm_probe' | grep -v grep"],
                         capture_output=True, text=True, timeout=15)
    print(out.stdout or "(none)")
except Exception as e:
    print("ps err", e)

print("--- UDP sockets 14540/14550 ---")
try:
    out = subprocess.run(["bash", "-c",
                          "ss -ulpn | grep -E ':14540|:14550' || echo '(none listed)'"],
                         capture_output=True, text=True, timeout=15)
    print(out.stdout or "(none)")
except Exception as e:
    print("ss err", e)

print("DONE")
