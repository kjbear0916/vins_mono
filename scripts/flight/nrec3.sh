#!/bin/bash
L=/tmp/nrec3.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

# THIS container was JUST docker-restarted -> native entrypoint chain is
# bringing up master+px4+gazebo. Do nothing but WAIT for px4 then record.
PX4UP=0
for i in $(seq 1 60); do
  if pgrep -ax px4 >/dev/null 2>&1; then
    echo "==PX4_UP_AT_${i}s=$(date -u +%H:%M:%S)==" >> "$L"; PX4UP=1; break
  fi
  sleep 2
done

if [ "$PX4UP" = 0 ]; then
  echo "==PX4_NEVER_UP==" >> "$L"; cat "$L"; exit 1
fi

# give gazebo camera plugin a beat to spin up
sleep 10

echo "==TOPIC_LIST_NATIVE==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311
timeout 25 rostopic list 2>&1 | grep -iE 'cam|image|imu|imu0|image_raw' | head -12 >> "$L" 2>&1

echo "==NATIVE_TOPIC_TOTAL==" >> "$L"
timeout 20 rostopic list 2>&1 | wc -l >> "$L" 2>&1

# record BOTH cam0+imu0 30s (the self-record deliverable)
mkdir -p /root/deliv
B=/root/deliv/native_$(date -u +%H%M%S).bag
echo "==REC=$B==" >> "$L"
timeout 62 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 32 > /tmp/nrec3_rec.log 2>&1
echo "==REC_END=$(date -u +%H:%M:%S)==" >> "$L"

echo "==AUDIT_BAG==" >> "$L"
ls -la "$B" >> "$L" 2>&1
timeout 45 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|topics|/cam0|/imu0' | head -12 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
