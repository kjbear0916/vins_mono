#!/bin/bash
# SINGLE atomic relaunch + audit passthrough.
# 1) kill the entire sitl chain (gzserver/px4/sitl_run), keep roscore
# 2) relaunch px4 from the PROVEN full-rate model (gazebo-classic iris_fpv_cam)
# 3) source ros, wait for px4 up, then WHILE PX4 IS FULL-RATE:
#    - rostopic list | grep for the camera/imu topics
#    - record actual bytes flowing on each candidate (104+107), prove the link alive
L=/tmp/audit0.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"

pkill -x gzserver 2>/dev/null; pkill -x px4 2>/dev/null
pkill -f sitl_run.sh 2>/dev/null; sleep 4
echo "==KILLED=$(date -u +%H:%M:%S)==" >> "$L"

source /opt/ros/noetic/setup.bash
cd /root/PX4-Autopilot/build/px4_sitl_default
DISPLAY=:99 nohup bash /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_run.sh \
  /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 none iris_fpv_cam empty \
  /root/PX4-Autopilot /root/PX4-Autopilot/build/px4_sitl_default > /tmp/sim_audit.log 2>&1 &
echo "==RELAUNCHED=$(date -u +%H:%M:%S)==" >> "$L"

# wait px4 up (full rate window)
for i in $(seq 1 90); do
  pgrep -x px4 >/dev/null && echo "==PX4_UP_AT_${i}s=$(date -u +%H:%M:%S)==" >> "$L" && break
  sleep 1
done

# NOW with px4 alive: enumerate camera/imu topics (this decides recordability)
echo "==TOPICS_CAM_IMU==" >> "$L"
timeout 30 rostopic list 2>&1 | grep -iE 'img|image|cam|imu|opt' | head -24 >> "$L" 2>&1

echo "==ALL_TOPIC_COUNT==" >> "$L"
timeout 30 rostopic list 2>&1 | wc -l >> "$L" 2>&1

# byte-flow audit on the candidate class 104/107 (compass2-style channel)
echo "==104_BYTES==" >> "$L"
timeout 20 python3 -c "
import socket
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(('0.0.0.0',14540))
s.settimeout(3)
n=0;t0=__import__('time').time()
try:
    while __import__('time').time()-t0<8:
        d,_=s.recvfrom(4096); n+=len(d)
except socket.timeout: pass
print('BYTES_8s=%d' % n)
" >> "$L" 2>&1

echo "==E=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
