#!/bin/bash
# Window IS open (px4 stdout = full-rate IMU callbacks, companion feeding).
# Record cam0+imu0 25s into a fixed-name bag, then audit. No inline quotes,
# no &&, no $() at the shell layer above. All in-file.
L=/tmp/wfront.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

source /opt/ros/noetic/setup.bash
export ROS_MASTER_URI=http://localhost:11311

echo "==PX4_CHECK==" >> "$L"
pgrep -ax px4 >> "$L" 2>&1

echo "==TOPIC_CHECK==" >> "$L"
timeout 20 rostopic list 2>&1 | grep -iE 'cam0|imu0|image|imu' | head -10 >> "$L" 2>&1

mkdir -p /root/vinsbones
B=/root/vinsbones/front_$(date -u +%H%M%S).bag
echo "==BAG=$B==" >> "$L"
echo "==REC_START=$(date -u +%H:%M:%S)==" >> "$L"
timeout 50 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 25 > /tmp/wfront_rec.log 2>&1
echo "==REC_END=$(date -u +%H:%M:%S)==" >> "$L"

echo "==BAG_AUDIT==" >> "$L"
ls -la "$B" >> "$L" 2>&1
timeout 40 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|topics|/cam0|/imu0' | head -10 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
