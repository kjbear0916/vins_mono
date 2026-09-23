#!/bin/bash
source /opt/ros/noetic/setup.bash
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
export DISPLAY=:0
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null; sleep 2
# no xvfb, no ros plugins
timeout 50 gzserver --verbose \
  /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/empty.world \
  >/tmp/fresh16_gz.log 2>&1 &
GZPID=$!
sleep 10
echo "=== gzserver alive ==="
ps -p $GZPID -o pid,stat,args 2>/dev/null | head -3
echo "=== spawn model ==="
timeout 20 gz model --verbose --spawn-file=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris_fpv_cam/iris_fpv_cam.sdf --model-name=iris_fpv_cam -x 1.01 -y 0.98 -z 0.83 2>&1 | head -10
sleep 5
echo "=== topics ==="
timeout 5 gz topic -l 2>/dev/null | grep -E 'mag|baro|imu|ground' | head
echo "=== mag hz ==="
timeout 8 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -3
echo "=== MAGDBG ==="
grep -a 'MAGDBG' /tmp/fresh16_gz.log | head -8
echo "=== errors ==="
grep -aE 'Err|Failed|error|EXCEPTION' /tmp/fresh16_gz.log | head -5
kill -9 $GZPID 2>/dev/null
echo DONE