#!/bin/bash
# Atomic final: restart happens BEFORE this (native window). Inside we ONLY
# (1) source ros, (2) wait 150s for cold gazebo, (3) audit topic names+types,
# (4) if cam0+imu0 exist -> record 40s -> bag audit. NO relaunch, NO pkill px4,
# NO own gzserver spawn. Pure window-area consumer.
L=/tmp/winB.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

echo "==PX4_PROC==" >> "$L"; pgrep -ax px4 >> "$L" 2>&1 || echo NONE >> "$L"
echo "==GZPROC==" >> "$L"; pgrep -ax gzserver >> "$L" 2>&1 || echo NONE >> "$L"

echo "==COLD_SLEEP_150s_FOR_NATIVE_GZ_CAM_REG=" >> "$L"
sleep 150

echo "==TOPIC_LIST_AFTER_150s==" >> "$L"
timeout 30 rostopic list 2>&1 | grep -iE 'cam|image|imu0|imu|mavros|px4|mavlink' | head -20 >> "$L" 2>&1
echo "==TOTAL_TOPIC_CNT==" >> "$L"
timeout 25 rostopic list 2>&1 | wc -l >> "$L" 2>&1

echo "==TYPE_PROBE_CAM0==" >> "$L"
timeout 20 rostopic type /cam0/image_raw 2>&1 | head -3 >> "$L" 2>&1
echo "==TYPE_PROBE_IMU0==" >> "$L"
timeout 20 rostopic type /imu0 2>&1 | head -3 >> "$L" 2>&1
echo "==TYPE_PROBE_IMU0_UNSLA==" >> "$L"
timeout 20 rostopic type /imu0_unsl 2>&1 | head -3 >> "$L" 2>&1

# decide & record
C=$(timeout 15 rostopic type /cam0/image_raw 2>&1 | head -1)
I=$(timeout 15 rostopic type /imu0 2>&1 | head -1)
if [ -n "$C" ] && [ -n "$I" ]; then
  mkdir -p /root/selfwin
  B=/root/selfwin/win_$(date -u +%H%M%S).bag
  echo "==REC_BAG=$B ==" >> "$L"
  echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
  timeout 80 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 42 > /tmp/win_rec.log 2>&1
  echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
  echo "==BAG_BYTES==" >> "$L"
  ls -la "$B" >> "$L" 2>&1
  echo "==BAG_INFO==" >> "$L"
  timeout 40 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics:' | head -12 >> "$L" 2>&1
else
  echo "==NOT_RECORDED_CAM0=$C IMU0=$I==" >> "$L"
fi
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
