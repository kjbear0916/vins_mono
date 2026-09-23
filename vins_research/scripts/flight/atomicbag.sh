#!/bin/bash
# THE atomic self-record: docker restart (native boot) already fired OUTSIDE.
# Inside: (1) companion binds 0.0.0.0:14540 NOW (server-first, so px4 boot
# finds it and opens the proven full-rate window), (2) wait px4, (3) record
# cam0+imu0 40s, (4) audit real bag bytes. All in this ONE file.
L=/tmp/atomic_bag.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

export ROS_MASTER_URI=http://localhost:11311
source /opt/ros/noetic/setup.bash 2>/dev/null

# (1) companion FIRST, server bind
if [ -f /tmp/companion_ready.py ]; then
  nohup python3 /tmp/companion_ready.py > /tmp/atomic_cmp.log 2>&1 &
  echo "==COMP_STARTED PID=$!" >> "$L"
else
  echo "==NO_COMPANION_READY==" >> "$L"
fi

# (2) wait px4 up (native chain, up to 90s)
for i in $(seq 1 90); do
  pgrep -x px4 >/dev/null 2>&1 && { echo "==PX4_UP_AT_${i}s=$(date -u +%H:%M:%S)==" >> "$L"; break; }
  sleep 1
done
pgrep -x px4 >/dev/null 2>&1 || { echo "==PX4_NEVER==" >> "$L"; cat "$L"; exit 1; }

# topics audit (does the native window actually expose cam0/imu0?)
echo "==TOPIC_AUDIT==" >> "$L"
timeout 20 rostopic list 2>&1 | grep -iE 'cam0|image|cam|imu' | head -10 >> "$L" 2>&1

# (3) record for ~40s
B=/root/catkin_ws/src/VINS-Mono/self_$(date -u +%H%M%S).bag
echo "==RECORDING_TO=$B==" >> "$L"
timeout 55 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 40 > /tmp/atomic_rec.log 2>&1
echo "==REC_END=$(date -u +%H:%M:%S)==" >> "$L"

# (4) bag audit
ls -la "$B" 2>&1 | grep -v 'No such' >> "$L"
if [ -f "$B" ]; then
  timeout 40 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -12 >> "$L" 2>&1
fi
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
