#!/bin/bash
L=/tmp/step31.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311
UP=0
for i in $(seq 1 60); do
  if pgrep -x px4 >/dev/null 2>&1; then UP=1; echo "==PX4_UP_AT=${i}x2s=$(date -u +%H:%M:%S)==" >> "$L"; break; fi
  sleep 2
done
if [ "$UP" != 1 ]; then echo "==PX4_NEVER_BAG==" >> "$L"; cat "$L"; exit 1; fi
sleep 6
echo "==NATIVE_TOPICS_AUDIT==" >> "$L"
timeout 25 rostopic list 2>&1 | grep -iE 'cam|image|imu|px4|mavros' | head -18 >> "$L" 2>&1
echo "==TYPES==" >> "$L"
T1=$(timeout 15 rostopic type /cam0/image_raw 2>&1)
T2=$(timeout 15 rostopic type /imu0 2>&1)
echo "CAM0_IMAGE_RAW=$T1" >> "$L" 2>&1
echo "IMU0=$T2" >> "$L" 2>&1
if [ -n "$T1" ] && [ -n "$T2" ]; then
  mkdir -p /root/selfeuroc
  B=/root/selfeuroc/step_$(date -u +%H%M%S).bag
  echo "==REC_BAG=$B==" >> "$L"
  echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
  timeout 56 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 42 > /tmp/step_rec.log 2>&1
  echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
  ls -la "$B" >> "$L" 2>&1
  echo "==BAG_AUDIT==" >> "$L"
  timeout 40 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -12 >> "$L" 2>&1
else
  echo "==TOPICS_MISSING_BAG_SKIPPED==" >> "$L"
fi
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
