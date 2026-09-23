#!/bin/bash
cd /root/PX4-Autopilot/build/px4_sitl_default/rootfs/log/2026-09-15 || exit 1
for f in *.ulg; do
  echo "== $f =="
  grep -aoE 'Arming denied[^[:cntrl:]]{0,60}|Preflight Fail[^[:cntrl:]]{0,60}|Armed by[^[:cntrl:]]{0,20}|Transition denied[^[:cntrl:]]{0,60}' "$f" 2>/dev/null | head -8
done