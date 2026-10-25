#!/bin/bash
L=/tmp/mbag_log.txt
: > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash
export ROS_MASTER_URI=http://localhost:11311

echo "==PX4=" >> "$L"
pgrep -ax px4 | head -1 >> "$L" 2>&1

echo "==ODE_BAG_BYTES_CAM0=" >> "$L"
timeout 12 rostopic echo -n1 /cam0/image_raw 2>&1 | grep -m1 -E 'seq: |height: |width: |encoding' >> "$L" 2>&1

echo "==ODE_BAG_BYTES_IMU0=" >> "$L"
timeout 12 rostopic echo -n1 /imu0 2>&1 | grep -m1 -E 'seq: |secs: |header' >> "$L" 2>&1

mkdir -p /root/selfrec
B=/root/selfrec/euroc_$(date -u +%H%M%S).bag
echo "==REC= $B  (30s)==" >> "$L"
timeout 80 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 28 > /tmp/mbag_rec2.log 2>&1
echo "==REC_END=$(date -u +%H:%M:%S)==" >> "$L"

echo "==BAG_BYTES=" >> "$L"
ls -la /root/selfrec/*.bag >> "$L" 2>&1

echo "==BAG_INFO==" >> "$L"
timeout 45 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0/image_raw|/imu0|topics:' >> "$L" 2>&1

echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
