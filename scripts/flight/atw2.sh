#!/bin/bash
L=/tmp/atw2.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311

# gazebo-classic cold-start = 120-180s; companion must be in window from sec 0
CP=/tmp/companion4.py
[ -f "$CP" ] || CP=$(find /root /tmp -maxdepth 7 -name 'companion*.py' 2>/dev/null | grep -viE 'test|~' | head -1)
echo "==COMP=$CP==" >> "$L"

# start companion in THIS window (it does NOT spawn/kill sim; only binds 14540)
nohup python3 "$CP" > /tmp/atw2_cmp.log 2>&1 &
echo "==COMP_PID=$! $(date -u +%H:%M:%S)==" >> "$L"

# wait px4 up (up to 240s; do nothing else that could kill the chain)
PX=0
for i in $(seq 1 120); do
  if pgrep -ax px4 | grep -q '/root/PX4-Autopilot'; then PX=1; echo "==PX4_UP_AT_${i}x2s=$(date -u +%H:%M:%S)==" >> "$L"; break; fi
  sleep 2
done
[ "$PX" = 1 ] || { echo "==PX4_NEVER_BAG_SKIPPED==" >> "$L"; cat "$L"; exit 1; }

# gazebo needs to register the camera plugin topic; give it the FULL cold duration
echo "==GZ_COLD_WAIT_150s==" >> "$L"
sleep 150

echo "==TOPIC_AUDIT==" >> "$L"
timeout 30 rostopic list 2>&1 | grep -iE 'cam0|image|imu0|imu' | head -14 >> "$L" 2>&1

CB=""

# record a 45s bag with cam+imu IF the topics are truly published
TA=$(timeout 16 rostopic type /cam0/image_raw 2>&1)
TI=$(timeout 16 rostopic type /imu0 2>&1)
echo "==TYPES cam0=$TA imu0=$TI==" >> "$L"
if [ -n "$TA" ] && [ -n "$TI" ]; then
  mkdir -p /root/atwbag
  B=/root/atwbag/atw_$(date -u +%H%M%S).bag
  echo "==REC_BAG=$B $(date -u +%H:%M:%S)==" >> "$L"
  timeout 60 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 45 > /tmp/atw2_rec.log 2>&1
  echo "==REC_DONE=$(date -u +%H:%M:%S)==" >> "$L"
  echo "==BAG_CANDIDATE==" >> "$L"
  ls -la "$B" >> "$L" 2>&1
  echo "==BAG_AUDIT==" >> "$L"
  timeout 40 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -12 >> "$L" 2>&1
  CB="$B"
else
  echo "==NO_CAM_TYPE_BAGSKIP==" >> "$L"
fi

echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
