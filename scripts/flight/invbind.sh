#!/bin/bash
L=/tmp/inv.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
export PYTHONUNBUFFERED=1

# STEP 1: bind the companion NOW (server-first, binds 0.0.0.0:14540, sends
# HEARTBEAT+OFFBOARD at 10Hz forever). pkill any oslates of old companions.
pkill -f 'companion' 2>/dev/null; sleep 2
CP=/root/catkin_ws/src/VINS-Mono/companion4.py
[ -f "$CP" ] || CP=/root/catkin_ws/src/VINS-Mono/companion3.py
[ -f "$CP" ] || CP=$(find /root /tmp -maxdepth 6 -name 'companion*.py' 2>/dev/null | grep -viE 'test|~' | head -1)
echo "==COMP=$CP==" >> "$L"
if [ -n "$CP" ] && [ -f "$CP" ]; then
  nohup python3 "$CP" > /tmp/inv_cmp.log 2>&1 &
  echo "==COMP_PID=$! BOUND_AT=$(date -u +%H:%M:%S)==" >> "$L"
else
  echo "==NO_COMPANION_FOUND==" >> "$L"
  exit 1
fi
sleep 4
# verify bind
ss -lntup 2>/dev/null | grep -E '14540|14550' | head -4 >> "$L" 2>&1 || netstat -lntup 2>/dev/null | grep -E '14540|14550' | head -4 >> "$L" 2>&1
echo "==__MARKER_DOCKER_RESTART_NOW__==" >> "$L"
