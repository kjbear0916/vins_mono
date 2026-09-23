#!/bin/bash
L=/tmp/nb3.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
echo "==PX4_NOW="; pgrep -ax px4 >> "$L" 2>&1

# 原生窗裡 master 在哪、topic 到底發不發 —— 直接 desc 拿 type(零寶)
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311
for t in /cam0/image_raw /cam0/cam_info /imu0 /mavros/imu/data_raw; do
  echo "==PROBE_$t== >> "$L"
  timeout 12 rostopic type "$t" 2>&1 >> "$L"
done

echo "==ALL_TOPICS_IMU_CAM==" >> "$L"
timeout 15 rostopic list 2>&1 | grep -iE 'cam|image|imu' | head -12 >> "$L" 2>&1

# 若 /cam0 存在 -> 直播證 bytes(不錄 bag,先看頂即時流 3s)
echo "==ECHO_CAM01=" >> "$L"
timeout 15 rostopic echo -n1 /cam0/image_raw 2>&1 | head -8 >> "$L" 2>&1
echo "==ECHO_IMU01=" >> "$L"
timeout 15 rostopic echo -n1 /imu0 2>&1 | head -8 >> "$L" 2>&1

echo "==RECORD_OPEN_WINDOW_35s=" >> "$L"
mkdir -p /root/simrecord
B=/root/simrecord/native_$(date -u +%H%M%S).bag
timeout 90 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 45 > /tmp/nb3_rec.log 2>&1
echo "==REC_END=$(date -u +%H:%M:%S)==" >> "$L"
ls -la "$B" >> "$L" 2>&1
echo "==BAG_INFO==" >> "$L"
timeout 40 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam|cam_info|/imu0|topics' | head -12 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
