#!/bin/bash
# ATOMIC native-window self-record. ONE file, runs INSIDE freshly-restarted
# container. Wait px4 up (up to 300s, gazebo-classic iris cam cold). When px4
# is up, audit cam0+imu0 types; if both real -> record 45s bag then audit bag.
# Never relaunches, never pkills any px4/gz process.
L=/tmp/atnw.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

echo "==WAIT_PX4_UP_TO_330s==" >> "$L"
UP=0
for i in $(seq 1 165); do
  if pgrep -ax px4 >/dev/null 2>&1; then
    echo "  PX4_UP_AT_$((i*2))s=$(date -u +%H:%M:%S)" >> "$L"; UP=1; break
  fi
  sleep 2
done
[ "$UP" = 1 ] || { echo "==PX4_NEVER_UP_BAG_IMPOSSIBLE==" >> "$L"; cat "$L"; exit 1; }

# gazebo iris camera still registering; give 60s
sleep 90

echo "==TOPIC_AUDIT==" >> "$L"
timeout 25 rostopic list 2>&1 | grep -iE 'cam0|cam|image|imu0|imu|mavros|px4' | head -20 >> "$L" 2>&1

C1=$(timeout 15 rostopic type /cam0/image_raw 2>&1)
C2=$(timeout 15 rostopic type /imu0 2>&1)
C3=$(timeout 15 rostopic type /cam0/cam_info 2>&1)
echo "  cam0/image_raw=$C1" >> "$L" 2>&1
echo "  imu0=$C2" >> "$L" 2>&1
echo "  cam0/cam_info=$C3" >> "$L" 2>&1

if [ -n "$C1" ] && [ -n "$C2" ]; then
  mkdir -p /root/atnw
  B=/root/atnw/atnw_$(date -u +%H%M%S).bag
  echo "==REC=$B==" >> "$L"
  echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
  timeout 90 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 45 >> "$L" 2>&1
  echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
  ls -la "$B" >> "$L" 2>&1
  echo "==BAG_AUDIT==" >> "$L"
  timeout 40 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -10 >> "$L" 2>&1
else
  echo "==CAM0_IMU0_MISSING_BAG_SKIPPED==  C1=$C1 C2=$C2" >> "$L"
fi
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
