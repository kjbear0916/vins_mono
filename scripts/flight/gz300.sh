#!/bin/bash
# The TRUTH: native entrypoint chain cold-boots gazebo-classic 90-150s.
# Self-record window OPENS when native gzserver registers /cam0/image_raw
# type. We do NOT spawn gzserver (that would kill the native one); we WAIT.
L=/tmp/gz300.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

echo "==WAIT_PX4_UP_TO_150s==" >> "$L"
PUP=0
for i in $(seq 1 75); do
  if pgrep -x px4 >/dev/null 2>&1; then PUP=1; echo "  PX4_UP_AT_${i}x2s=$(date -u +%M:%S)" >> "$L"; break; fi
  sleep 2
done

echo "==NATIVE_GZSERVER_ONLY(no spawn)== " >> "$L"
pgrep -ax gzserver | head -2 >> "$L" 2>&1

# wait cam0/image_raw TYPE up to 240s (native chain cold-boot camera plugin)
CT=0
for i in $(seq 1 120); do
  T=$(timeout 16 rostopic type /cam0/image_raw 2>&1)
  if echo "$T" | grep -qi sensor_msgs; then CT=1; echo "  CAM0_TYPE_UP_AT_${i}x2s=$(date -u +%M:%S):$T" >> "$L"; break; fi
  sleep 2
done
[ "$CT" = 1 ] || { echo "==CAM0_NEVER_UP_IN_240s==" >> "$L"; cat "$L"; exit 1; }

IT=0
for i in $(seq 1 30); do
  T=$(timeout 16 rostopic type /imu0 2>&1)
  if echo "$T" | grep -qi sensor_msgs; then IT=1; echo "  IMU0_TYPE_UP_AT_${i}x2s:$T" >> "$L"; break; fi
  sleep 2
done

mkdir -p /root/selfeuroc99
B=/root/selfeuroc99/win_$(date -u +%H%M%S).bag
echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
timeout 70 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 60 > /tmp/gz300_rec.log 2>&1
echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
ls -la "$B" >> "$L" 2>&1
echo "==BAG_AUDIT==" >> "$L"
timeout 45 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -12 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
