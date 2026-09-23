#!/bin/bash
L=/tmp/pull2.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

echo "==PX4=" >> "$L"; pgrep -ax px4 >> "$L" 2>&1 || echo NONE >> "$L"
echo "==GZSERVER=" >> "$L"; pgrep -ax gzserver >> "$L" 2>&1 || echo NONE >> "$L"
echo "==COMPANION=" >> "$L"; pgrep -af 'companion' >> "$L" 2>&1 || echo NONE >> "$L"

echo "==TOPIC_TYPE_NOW==" >> "$L"
T1=$(timeout 20 rostopic type /cam0/image_raw 2>&1 | head -1)
T2=$(timeout 20 rostopic type /imu0 2>&1 | head -1)
T3=$(timeout 20 rostopic type /cam0/cam_info 2>&1 | head -1)
T4=$(timeout 20 rostopic type /imu0_unsl 2>&1 | head -1)
echo "  /cam0/image_raw => $T1" >> "$L" 2>&1
echo "  /imu0          => $T2" >> "$L" 2>&1
echo "  /cam0/cam_info => $T3" >> "$L" 2>&1
echo "  /imu0_unsl     => $T4" >> "$L" 2>&1

echo "==ANY_CAM0_IMU0_PRESENT==" >> "$L"
C=0; I=0
[ -n "$T1" ] && C=1
[ -n "$T2" ] && I=1
echo "  CAM0_PRESENT=$C  IMU0_PRESENT=$I" >> "$L"

if [ "$C" = 1 ] && [ "$I" = 1 ]; then
  mkdir -p /root/selfwin
  B=/root/selfwin/native_$(date -u +%H%M%S).bag
  echo "==REC_BAG=$B==" >> "$L"
  echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
  timeout 100 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 58 >> "$L" 2>&1
  echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
  ls -la "$B" >> "$L" 2>&1
  echo "==BAG_AUDIT==" >> "$L"
  timeout 50 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -14 >> "$L" 2>&1
else
  echo "==TOPIC_MISSING_CAM0=$C IMU0=$I BAG_SKIP==" >> "$L"
  echo "==GZ_SELF_DIAG==" >> "$L"
  timeout 25 gz topic -l 2>&1 | grep -iE 'cam|image|imu' | head -8 >> "$L" 2>&1
fi

echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
