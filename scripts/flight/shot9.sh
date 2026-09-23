#!/bin/bash
L=/tmp/snapshot9.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

echo "==PX4_PROC==" >> "$L"
pgrep -ax px4 >> "$L" 2>&1 || echo NONE >> "$L"
echo "==GZSERVER==" >> "$L"
pgrep -ax gzserver >> "$L" 2>&1 || echo NONE >> "$L"

echo "==TCP_DUMP_6S_ANY_14540_14550==" >> "$L"
timeout 8 tcpdump -i any -nn -l "udp port 14540 or udp port 14550" > /tmp/snap_dump.txt 2>&1
wc -l < /tmp/snap_dump.txt >> "$L" 2>&1
head -3 /tmp/snap_dump.txt >> "$L" 2>&1

echo "==TOPICS_CAM_IMU==" >> "$L"
source /opt/ros/noetic/setup.bash
export ROS_MASTER_URI=http://localhost:11311
timeout 18 rostopic list 2>&1 | grep -iE 'cam|imu|image|px4' | head -14 >> "$L" 2>&1

echo "==ALL_TOPIC_COUNT==" >> "$L"
timeout 18 rostopic list 2>&1 | wc -l >> "$L" 2>&1

mkdir -p /root/shotmsgs
B=/root/bagsnap_9_$(date -u +%H%M%S).bag
echo "==REC_30s_BAG=$B==" >> "$L"
timeout 70 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 28 > /tmp/snap_rec9.log 2>&1
echo "==REC_END=$(date -u +%H:%M:%S)==" >> "$L"
ls -la "$B" >> "$L" 2>&1
echo "==BAG_INFO==" >> "$L"
timeout 30 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -10 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
