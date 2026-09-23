#!/bin/bash
# Moves ONLY inside the current window (companion was bound before restart, so
# px4 booted into a server already waiting = the one proven full-rate posture).
# Exactly ONE audit + record. NO pkill, NO relaunch, NO gazebo touch.
L=/tmp/wfin.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

echo "==ALIVE_AUDIT==" >> "$L"
pgrep -ax px4 >> "$L" 2>&1 || echo PX4_NONE >> "$L"
pgrep -ax gzserver >> "$L" 2>&1 || echo GZ_NONE >> "$L"
for c in /root/catkin_ws/src/VINS-Mono/companion4.py /tmp/companion4.py /root/companion4.py; do
  [ -f "$c" ] && echo "COMP_FILE=$c" >> "$L"
done

echo "==WAIT_CAM0_TYPE_UP_TO_200s==" >> "$L"
FOUND=0
for i in $(seq 1 100); do
  T=$(timeout 13 rostopic type /cam0/image_raw 2>&1)
  if echo "$T" | grep -qi sensor_msgs; then
    echo "  CAM0_TYPE_UP_AT_$((i*2))s=$(date -u +%M:%S): $T" >> "$L"; FOUND=1; break
  fi
  sleep 2
done

if [ "$FOUND" = 1 ]; then
  echo "==IMU_TYPE_PROBE==" >> "$L"
  IT=$(timeout 13 rostopic type /imu0 2>&1)
  echo "  IMU0=$IT" >> "$L" 2>&1
  mkdir -p /root/windbg
  B=/root/windbg/w_$(date -u +%H%M%S).bag
  echo "==REC_BAG=$B==" >> "$L"
  echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
  if [ -n "$IT" ] && echo "$IT" | grep -qi sensor_msgs; then
    timeout 88 rosbag record --duration 58 -O "$B" /cam0/image_raw /imu0 > /tmp/w_rec.log 2>&1
  else
    timeout 88 rosbag record --duration 58 -O "$B" /cam0/image_raw > /tmp/w_rec.log 2>&1
  fi
  echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
  ls -la "$B" >> "$L" 2>&1
  echo "==BAG_AUDIT==" >> "$L"
  timeout 15 rosbag width "$B" >> "$L" 2>&1
  timeout 50 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -12 >> "$L" 2>&1
else
  echo "==CAM0_NEVER_BAG_IMPOSSIBLE==" >> "$L"
  echo "==TOPIC_SAMPLE==" >> "$L"
  timeout 15 rostopic list 2>&1 | grep -iE 'cam|imu|image|px4|mav' | head -14 >> "$L" 2>&1
fi
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
