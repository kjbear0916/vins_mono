#!/bin/bash
# docker restart gives the ONLY proven full-rate window. We enter it IMMEDIATELY
# after restart with a pure audit-then-record (NEVER kills px4/gzserver).
L=/tmp/win_grab.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

# wait px4 native up (up to 180s) — do NOT touch it once up
UP=0
for i in $(seq 1 90); do
  if pgrep -x px4 >/dev/null 2>&1; then UP=1; echo "==PX4_UP_AT=${i}x2s=$(date -u +%H:%M:%S)==" >> "$L"; break; fi
  sleep 2
done
[ "$UP" = 1 ] || { echo "==PX4_NEVER__BAG_IMPOSSIBLE==" >> "$L"; cat "$L"; exit 1; }

# small settle for gazebo cameras to register
sleep 8

echo "==ALL_TOPIC_AUDIT==" >> "$L"
timeout 25 rostopic list 2>&1 | grep -iE 'cam|image|imu|px4|mavros|mavlink' | head -18 >> "$L" 2>&1

echo "==CAM0_TYPE==" >> "$L"
timeout 15 rostopic type /cam0/image_raw 2>&1 | head -2 >> "$L" 2>&1
echo "==IMU0_TYPE==" >> "$L"
timeout 15 rostopic type /imu0 2>&1 | head -2 >> "$L" 2>&1

# if both types exist -> record 30s into a named bag
T1=$(timeout 15 rostopic type /cam0/image_raw 2>&1)
T2=$(timeout 15 rostopic type /imu0 2>&1)
if [ -n "$T1" ] && [ -n "$T2" ]; then
  mkdir -p /root/selfeuroc
  B=/root/selfeuroc/win_$(date -u +%H%M%S).bag
  echo "==REC_BAG=$B==" >> "$L"
  echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
  timeout 100 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 55 > /tmp/winrec.log 2>&1
  echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
  echo "==BAG_BYTES==" >> "$L"
  ls -la "$B" >> "$L" 2>&1
  echo "==BAG_AUDIT==" >> "$L"
  timeout 45 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -12 >> "$L" 2>&1
else
  echo "==NO_CAM0_IMU0_TYPES_BAG_SKIPPED==" >> "$L"
fi

echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
