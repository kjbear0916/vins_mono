#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export HEADLESS=1
export NO_PXH=1
export PX4_SIM_MODEL=gazebo-classic_iris
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
export GAZEBO_MASTER_URI=http://127.0.0.1:11345
export PX4_SIM_MODEL=gazebo-classic_iris
# start gzserver directly with output to file, same world/args as sitl_run.sh
xvfb-run -a -s '-screen 0 1920x1080x24' gzserver --verbose \
  /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/empty.world \
  -s libgazebo_ros_api_plugin.so -s libgazebo_ros_paths_plugin.so \
  >/tmp/fresh14_gz.log 2>&1 &
GZPID=$!
sleep 12

# spawn model like sitl_run.sh does
timeout 20 gz model --verbose --spawn-file=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris_fpv_cam/iris_fpv_cam.sdf --model-name=iris_fpv_cam -x 1.01 -y 0.98 -z 0.83 2>&1 | grep -v "^\[1;32m\|^\[1;33m\|^\[0m" | head -5
sleep 6

echo "=== gzserver alive? ==="
ps -eo pid,args | grep -a 'gzserver' | grep -v grep | head -3
echo "=== imu hz (needs px4? no) ==="
timeout 5 gz topic -z '/gazebo/default/iris_fpv_cam/imu' 2>&1 | head -3
echo "=== groundtruth hz ==="
timeout 5 gz topic -z '/gazebo/default/iris_fpv_cam/groundtruth' 2>&1 | head -3
echo "=== mag hz ==="
timeout 5 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -3
echo "=== MAGDBG ==="
grep -a 'MAGDBG' /tmp/fresh14_gz.log | head -8
echo "=== mag topic publisher? ==="
timeout 3 gz topic -i '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -5

kill -9 $GZPID 2>/dev/null; sleep 1
echo DONE