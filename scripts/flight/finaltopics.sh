#!/bin/bash
L=/tmp/finaltopics.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash
export ROS_MASTER_URI=http://localhost:11311

echo "==PX4_CHECK==" >> "$L"
pgrep -ax px4 >> "$L" 2>&1 || echo NONE >> "$L"

echo "==ALL_TOPICS_FULL==" >> "$L"
timeout 25 rostopic list 2>&1 | head -40 >> "$L"

echo "==CAM0_ECHO_1F=" >> "$L"
timeout 25 rostopic echo -n1 /cam0/image_raw 2>&1 | head -6 >> "$L"
echo "==IMU0_ECHO_1F=" >> "$L"
timeout 25 rostopic echo -n1 /imu0 2>&1 | head -8 >> "$L"

echo "==ENGINE=  NOW RECORD 25s (live window)" >> "$L"
mkdir -p /root/baglive
B=/root/baglive/finalwin_$(date -u +%H%M%S).bag
timeout 45 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 25 > /tmp/finalwin_rec.log 2>&1
echo "==REC_END=$(date -u +%H:%M:%S)==" >> "$L"
ls -la "$B" 2>&1 >> "$L"
echo "==BAG_AUDIT==" >> "$L"
timeout 30 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|topics|/cam0|/imu0' | head -10 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
