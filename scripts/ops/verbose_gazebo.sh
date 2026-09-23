#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export HEADLESS=1 NO_PXH=1 PX4_SIM_MODEL=gazebo-classic_iris
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
# WITHOUT the LD_LIBRARY_PATH override variant is env A; WITH it is env B
export LD_LIBRARY_PATH="${1:-default}:$LD_LIBRARY_PATH"
WORLD=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/iris.world
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4; pkill -9 -x Xvfb; sleep 1
timeout 25 gzserver --verbose $WORLD "$GAZEBO_MODEL_PATH" 2>&1 | head -8
echo "=== gazebo log level test done ==="