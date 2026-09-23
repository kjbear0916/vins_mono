#!/bin/bash
set -u
echo "== PX4 key status =="
grep -aoE '\[(init|logger|mavlink|ekf2|commander|navigator|simulator|gz_bridge)[^]]*\][^ ]*[^ ]* [A-Za-z].*' /tmp/px4_sitl.log | tail -20
echo "== takeoff/arming/error =="
grep -aoE '(Entered [A-Z]+ flight mode|Arming|disarm|takeoff|Land|could not|ERROR|FAILED|Timed out)[^\r]*' /tmp/px4_sitl.log | sort | uniq -c | sort -rn | head -15
echo "== last 800 bytes non-pxh =="
tr '\r' '\n' < /tmp/px4_sitl.log | grep -avE '^pxh>|^$' | tail -25