#!/bin/bash
# THE proven chain: docker restart NOT needed. sitl_run.sh (iris_fpv_cam,
# empty world) + companion in the SAME window, recorded to bag. This is the
# single most-successful recipe from wire60 era. NO pkill storms.
source /opt/ros/noetic/setup.bash 2>/dev/null
export ROS_MASTER_URI=http://localhost:11311
L=/tmp/atw.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

# Kill only companions we spawned earlier (never gz/px4/ros cores)
for c in /tmp/companion*.py /root/catkin_ws/src/VINS-Mono/companion4.py; do
  [ -f "$c" ] && pkill -f "$c" 2>/dev/null
done
sleep 2

# this time: if px4 already up, we keep the running chain (do NOT relaunch).
# if not, launch ONE native sitl_run (which gazebo cold 60-120s).
if ! pgrep -x px4 >/dev/null 2>&1; then
  echo "==NO_PX4_LAUNCH_CHAIN==" >> "$L"
  cd /root/PX4-Autopilot/build/px4_sitl_default
  nohup bash /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_run.sh \
    /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 none iris_fpv_cam empty \
    /root/PX4-Autopilot /root/PX4-Autopilot/build/px4_sitl_default \
    > /tmp/atw_sitl.log 2>&1 &
  echo "  SITL_PID=$!" >> "$L"
fi

# wait px4 + gazebo cold register
for i in $(seq 1 100); do
  if pgrep -x px4 >/dev/null 2>&1; then echo "  PX4_UP_AT_${i}x2s=$(date -u +%H:%M:%S)" >> "$L"; break; fi
  sleep 2
done

# companion from this SECOND (bind server 0.0.0.0:14540)
if [ -f /tmp/companion4.py ]; then
  nohup python3 /tmp/companion4.py > /tmp/atw_cmp.log 2>&1 &
  echo "  COMPANION4_PID=$! =$(date -u +%H:%M:%S)" >> "$L"
elif [ -f /root/catkin_ws/src/VINS-Mono/companion4.py ]; then
  nohup python3 /root/catkin_ws/src/VINS-Mono/companion4.py > /tmp/atw_cmp.log 2>&1 &
  echo "  COMPANION4_WS_PID=$! =$(date -u +%H:%M:%S)" >> "$L"
fi

# wait topics to actually register (gazebo camera plugin cold 30-60s after px4)
for i in $(seq 1 90); do
  T=$(timeout 16 rostopic type /cam0/image_raw 2>&1)
  if echo "$T" | grep -qi sensor_msgs; then
    echo "  CAM0_TYPE_UP_AT_${i}x2s: $T" >> "$L"; break
  fi
  sleep 3
done

# audit presence then record 40s
mkdir -p /root/selfatw
B=/root/selfatw/atw_$(date -u +%H%M%S).bag
echo "==REC_S=$(date -u +%H:%M:%S)==" >> "$L"
timeout 90 rosbag record -O "$B" /cam0/image_raw /imu0 --duration 40 > /tmp/atw_rec.log 2>&1
echo "==REC_E=$(date -u +%H:%M:%S)==" >> "$L"
ls -la "$B" >> "$L" 2>&1
echo "==BAG_AUDIT==" >> "$L"
timeout 40 rosbag info "$B" 2>&1 | grep -iE 'duration|messages|/cam0|/imu0|topics' | head -12 >> "$L" 2>&1
echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
