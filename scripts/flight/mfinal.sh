#!/bin/bash
# After docker restart (native sim chain). ONE exec. Companion from second-0.
L=/tmp/mfinal.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

# wait px4 up (native restart chain)
PX4W=0
for i in $(seq 1 90); do
  if pgrep -x px4 >/dev/null 2>&1; then PX4W=1; echo "==PX4_UP_AT_${i}s=$(date -u +%H:%M:%S)==" >> "$L"; break; fi
  sleep 1
done
[ "$PX4W" = 1 ] || { echo "==PX4_NEVER==" >> "$L"; cat "$L"; exit 1; }

# see master: where does rostopic really live in THIS env
source /opt/ros/noetic/setup.bash 2>/dev/null
echo "==MASTER_ENV=$ROS_MASTER_URI==" >> "$L"
echo "==TOP_LIST==" >> "$L"
timeout 20 rostopic list 2>&1 | head -20 >> "$L"

# companion: PROVEN files live in /tmp (companion.py), bind 0.0.0.0:14540
ls -la /tmp/companion*.py 2>&1 >> "$L"
COMP=/tmp/companion.py
[ -f "$COMP" ] || COMP=/tmp/companion3.py
[ -f "$COMP" ] || COMP=/root/catkin_ws/src/VINS-Mono/companion4.py
if [ -f "$COMP" ]; then
  nohup python3 "$COMP" > /tmp/mfinal_cmp.log 2>&1 &
  echo "==COMP=$COMP PID=$!" >> "$L"
else
  echo "==NO_COMPANION_ANYWHERE==" >> "$L"
fi

# give companion a moment, then record cam0+imu0
sleep 3
mkdir -p /root/euroc_self
B=/root/euroc_self/mfinal_$(date -u +%H%M%S).bag
echo "==REC_BAG=$B==" >> "$L"
echo "==REC_TOPICS_PRE==" >> "$L"
timeout 15 rostopic list 2>&1 | grep -iE 'cam|image|imu' | head >> "$L"
timeout 40 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 25 > /tmp/mfinal_rec.log 2>&1
echo "==REC_END=$(date -u +%H:%M:%S)==" >> "$L"
ls -la /root/euroc_self/*.bag 2>&1 >> "$L"
echo "==BAG_INFO==" >> "$L"
BL=$(ls -t /root/euroc_self/*.bag 2>/dev/null | head -1)
[ -n "$BL" ] && timeout 30 rosbag info "$BL" 2>&1 | grep -iE 'messages|duration|topics|/cam|/imu' | head -12 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
