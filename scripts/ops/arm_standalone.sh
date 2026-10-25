#!/bin/bash
# Standalone arming debug: fresh sim + raw-mavlink arm, verify param readback.
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash

pkill -9 -x px4 2>/dev/null
pkill -9 -x gzserver 2>/dev/null
pkill -9 -x Xvfb 2>/dev/null
pkill -9 -f 'xvfb-ru[n]' 2>/dev/null
pkill -9 -f 'sitl_run.s[h]' 2>/dev/null
sleep 2
nohup bash /root/sim_launch.sh >/tmp/arm_sim.log 2>&1 &

for i in $(seq 1 40); do
  r=$(timeout 6 rostopic hz /iris_fpv_cam/usb_cam/image_raw 2>/dev/null | awk '/average rate/ {print $3; exit}')
  if [ -n "$r" ]; then echo "CAM_OK $r"; break; fi
  sleep 2
done

python3 -u /tmp/mavlink_arm.py 2>&1 | tee /tmp/arm_standalone_out.log
echo "=== px4 tail ==="
tail -12 /tmp/arm_sim.log | grep -aiE 'preflight|arm|fail|param|notify|compass' | cut -c1-120