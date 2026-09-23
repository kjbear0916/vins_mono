#!/bin/bash
# PC1: wait cam0/image_raw type (gazebo cold 120-180s) then record 55s.
L=/tmp/pc1.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

echo "==PX4_NOW== " >> "$L"; pgrep -ax px4 >> "$L" 2>&1 || echo NONE >> "$L"
echo "==CMP_ALIVE== " >> "$L"; pgrep -af 'companion' >> "$L" 2>&1 || echo NONE >> "$L"

echo "==WAIT_CAM0_TYPE_UP_TO_240s==" >> "$L"
FOUND=0
for i in $(seq 1 240); do
  T=$(timeout 15 rostopic type /cam0/image_raw 2>&1)
  if echo "$T" | grep -qi sensor_msgs; then
    echo "  CAM0_TYPE_UP_AT_$i s: $T" >> "$L"; FOUND=1; break
  fi
  sleep 1
done
[ "$FOUND" = 1 ] || { echo "==CAM0_NEVER_UP_PX4=$([ -n "$(pgrep -x px4)" ] && echo ALIVE || echo DEAD)==" >> "$L"; cat "$L"; exit 1; }

ID=$(timeout 18 rostopic type /imu0 2>&1)
echo "  IMU0_TYPE=$ID" >> "$L" 2>&1
[ -z "$ID" ] && ID=NONE

mkdir -p /root/pc1bags
B=/root/pc1bags/pc1_$(date -u +%H%M%S).bag
echo "==REC=$B==" >> "$L"
echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
if [ "$ID" != NONE ]; then
  timeout 130 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 55 > /tmp/pc1_rec.log 2>&1
else
  timeout 130 rosbag record -O "$B" /cam0/image_raw --duration 55 > /tmp/pc1_rec.log 2>&1
fi
echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
ls -la "$B" >> "$L" 2>&1
echo "==AUDIT==" >> "$L"
timeout 40 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -12 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
