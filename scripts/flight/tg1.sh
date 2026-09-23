#!/bin/bash
# Everything gated on the REAL witness = topic /cam0/image_raw having a type.
# Not px4, not gzserver. This is the only probe that has EVER been "the window".
L=/tmp/tg1.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
#this script runs fresh after a docker restart (entrypoint sim chain is booting)
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

echo "==WAIT_TOPIC_CAM0_UP_TO_320s==" >> "$L"
FOUND=0
for i in $(seq 1 160); do
  T=$(timeout 15 rostopic type /cam0/image_raw 2>&1)
  if echo "$T" | grep -qi sensor_msgs; then
    echo "  cam0_type_up_after_$((i*2))s: $T" >> "$L"
    FOUND=1; break
  fi
  sleep 2
done

if [ "$FOUND" = 1 ]; then
  echo "==CM0_TYPE=$T==" >> "$L"
  I=$(timeout 15 rostopic type /imu0 2>&1)
  echo "==IMU0_TYPE=$I==" >> "$L"
  if [ -n "$I" ]; then
    mkdir -p /root/tgwinbags
    B=/root/tgwinbags/tg_$(date -u +%H%M%S).bag
    echo "==RECBAG=$B==" >> "$L"
    echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
    # companion must NOT be relaunched; just record with existing topics
    timeout 90 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 50 > /tmp/tg_rec.log 2>&1
    echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
    echo "==BAG_BYTES==" >> "$L"
    ls -la "$B" >> "$L" 2>&1
    echo "==BAG_AUDIT==" >> "$L"
    timeout 50 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics:' | head -12 >> "$L" 2>&1
  else
    echo "==IMU0_TYPE_MISSING_BAG_SKIPPED_IMU0=$I==" >> "$L"
  fi
else
  echo "==CAM0_NEVER_REG_=320s_BAG_IMPOSSIBLE==" >> "$L"
  timeout 25 rostopic list 2>&1 | grep -iE 'cam|image|imu|px4|mavros' | head -14 >> "$L" 2>&1
fi
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
