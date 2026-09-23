#!/bin/bash
source /root/catkin_ws/devel/setup.bash
source /opt/ros/noetic/setup.bash
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null; pkill -9 -f sitl_run.sh 2>/dev/null; sleep 2
# run gzserver directly, capture all output
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
export PX4_SIM_MODEL=gazebo-classic_iris
export NO_PXH=1
export HEADLESS=1
timeout 40 gzserver --verbose /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/empty.world -s libgazebo_ros_api_plugin.so -s libgazebo_ros_paths_plugin.so >/tmp/fresh10_gz.log 2>&1 &
GZPID=$!
sleep 8
# spawn model
timeout 15 gz model --verbose --spawn-file=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris_fpv_cam/iris_fpv_cam.sdf --model-name=iris_fpv_cam -x 1.01 -y 0.98 -z 0.83 2>&1 | head -5
sleep 3
echo "=== mag Hz ==="
timeout 4 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -2
echo "=== mag DBG lines ==="
grep -a 'MAGDBG' /tmp/fresh10_gz.log | head -10
echo "=== any plugin errors ==="
grep -aE 'Failed.*load|error|Error' /tmp/fresh10_gz.log | head -5
# start px4 in rootfs
cd /root/PX4-Autopilot/build/px4_sitl_default/rootfs
timeout 15 /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 -d /root/PX4-Autopilot/build/px4_sitl_default/etc >/tmp/fresh10_px4.log 2>&1 &
PX4_PID=$!
sleep 12
echo "=== PX4 connected? ==="
grep -a 'connected\|mavlink\|param' /tmp/fresh10_px4.log | head -5
echo "=== mag Hz after px4 ==="
timeout 4 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -2
kill -9 $GZPID $PX4_PID 2>/dev/null
echo "=== DONE ==="