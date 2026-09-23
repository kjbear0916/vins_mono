#!/bin/bash
# invert: companion binds FIRST (0.0.0.0:14540, server-first, companion4 proven),
# then `docker restart` reboots px4 INTO the waiting server = full-rate window.
L=/tmp/inv2.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

# find the best companion (companion4/companion3/companion.py exist on host /tmp)
CP=""
for c in /tmp/companion4.py /tmp/companion3.py /tmp/companion2.py /tmp/companion.py; do
  [ -f "$c" ] && { CP="$c"; break; }
done
[ -z "$CP" ] && CP=$(find /root /catkin_ws /tmp -maxdepth 6 -name 'companion*.py' 2>/dev/null | grep -viE 'test|~' | head -1)
echo "==COMP=$CP==" >> "$L"
[ -n "$CP" ] || { echo "==NO_COMPANION==" >> "$L"; exit 1; }

# bind first
python3 "$CP" > /tmp/inv_companion.log 2>&1 &
CPID=$!
echo "==COMP_BOUND_PID=$CPID=$(date -u +%H:%M:%S)==" >> "$L"
sleep 2

echo "==NOW_DOCKER_RESTART_RUN_NAME=vins_research==" >> "$L"
echo "==T=USER_RESTART_THEN_THIS=_PE=|WAIT_USED_PRE-BIND==" >> "$L"

# wait for the cam topic to actually register (after companion already bound)
echo "==WAIT_CAM0_UP_TO_360s==" >> "$L"
FOUND=0
for i in $(seq 1 180); do
  T=$(timeout 12 rostopic type /cam0/image_raw 2>&1)
  if echo "$T" | grep -qi sensor_msgs; then
    echo "  CAM0_TYPE_UP_AT_$((i*2))s: $T" >> "$L"; FOUND=1; break
  fi
  sleep 2
done
[ "$FOUND" = 1 ] || { echo "==CAM0_NEVER_AFTER_360s_BAG_IMPOSSIBLE==" >> "$L"; pkill -f "$CP" 2>/dev/null; cat "$L"; docker kill vins_research; exit 1; }

C2=$(timeout 12 rostopic type /imu0 2>&1); echo "  IMU0_TYPE=$C2" >> "$L" 2>&1
if [ -z "$C2" ] || ! echo "$C2" | grep -qi sensor_msgs; then
  echo "  IMU0_MISSING_BAG_CAM0_ONLY=" >> "$L"
  C2=/imu0; [ -n "$C2" ] || true
fi

mkdir -p /root/bagsel
B=/root/bagsel/prebound_$(date -u +%H%M%S).bag
echo "==REC_BAG=$B==" >> "$L"
echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
if echo "$C2" | grep -qi sensor_msgs; then
  timeout 110 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 60 > /tmp/pb_rec.log 2>&1
else
  timeout 110 rosbag record -O "$B" /cam0/image_raw --duration 60 > /tmp/pb_rec.log 2>&1
fi
echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
ls -la "$B" >> "$L" 2>&1
echo "==BAG_AUDIT==" >> "$L"
timeout 45 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -10 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
