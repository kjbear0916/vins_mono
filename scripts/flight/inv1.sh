#!/bin/bash
# Companion-first atomic: server is in place for the WHOLE boot so px4 comes
# up at the proven full-rate condition (companion4.py style: 0.0.0.0:14540
# UDPServer listener + 10Hz offboard; this is the ONE recipe that the bag
# record ever saw /cam0 + /imu0 registered with messages).
L=/tmp/inv1.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

# locate a proven companion file (the one that has a UDPServer + OFFBOARD)
C2=""
for x in /root/catkin_ws/src/VINS-Mono/companion*.py /root/companion*.py /tmp/companion*.py; do
  [ -f "$x" ] && python3 - "$x" <<'PY' 2>/dev/null && C2=$x && break
import sys
data=open(sys.argv[1]).read()
sys.exit(0 if ("UDPServer" in data and "TELEM2" in data) else 1)
PY
done
[ -n "$C2" ] || C2=/root/catkin_ws/src/VINS-Mono/companion4.py
[ -f "$C2" ] || C2=/tmp/companion4.py
echo "==COMP=$C2 EXISTS=$(test -f "$C2" && echo YES || echo NO)==" >> "$L"

# start companion NOW (before ship boot)
if [ -f "$C2" ]; then
  nohup python3 "$C2" > /tmp/inv_cmp.log 2>&1 &
  echo "==COMP_STARTED_PID=$! at $(date -u +%H:%M:%S)==" >> "$L"
  sleep 4
  echo "==BOUND_4520?==" >> "$L"
  ss -lntup 2>/dev/null | grep -E '14540|14550' | head -3 >> "$L" 2>&1 || netstat -lntup 2>/dev/null | grep -E '14540|14550' | head -3 >> "$L" 2>&1
else
  echo "==NO_COMPANION_FILE=" >> "$L"
fi

# companion is bound and waiting. Signal the OUTER restart to now docker
# restart the container (px4 will boot INTO this waiting server).
echo "==NEXT_DOCKER_RESTART_GO_PX4_BOOTS_INTO_BOUND_COMPANION==" >> "$L"
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
