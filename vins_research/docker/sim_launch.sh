#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export HEADLESS=1
export NO_PXH=1
export PX4_SIM_MODEL=gazebo-classic_iris
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:$LD_LIBRARY_PATH
/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_run.sh /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 none iris_fpv_cam empty /root/PX4-Autopilot /root/PX4-Autopilot/build/px4_sitl_default
