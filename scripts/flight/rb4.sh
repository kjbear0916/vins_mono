#!/bin/bash
L=/tmp/rb4.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

echo "==WAIT_CAM0_TYPE_UP_TO_240s==" >> "$L"
FOUND=0
for i in $(seq 1 120); do
  T=$(timeout 14 rostopic type /cam0/image_raw 2>&1)
  if echo "$T" | grep -qi sensor_msgs; then
    echo "  CAM0_TYPE_UP_AT_$((i*2))s: $T" >> "$L"; FOUND=1; break
  fi
  sleep 2
done

if [ "$FOUND" = 0 ]; then
  echo "==CAM0_NEVER__TOPIC_AUDIT==" >> "$L"
  timeout 25 rostopic list 2>&1 | grep -iE 'cam0|imu0|image|imu|mavros' | head -16 >> "$L" 2>&1
  echo "==E=$(date -u +%H:%M:%S)==" >> "$L"; cat "$L"; exit 1
fi

I=$(timeout 14 rostopic type /imu0 2>&1)
echo "  IMU0_TYPE=$I" >> "$L" 2>&1
[ -n "$I" ] || I=NONE

mkdir -p /root/euw1
B=/root/euw1/final_$(date -u +%H%M%S).bag
echo "==REC=$B==" >> "$L"
echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
if echo "$I" | grep -qi sensor_msgs; then
  timeout 100 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 55 > /tmp/rb4_rec.log 2>&1
else
  timeout 100 rosbag record -O "$B" /cam0/image_raw --duration 55 > /tmp/rb4_rec.log 2>&1
fi
echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
ls -la "$B" >> "$L" 2>&1
echo "==BAG_AUDIT==" >> "$L"
timeout 50 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -12 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
