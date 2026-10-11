#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export HEADLESS=1
export NO_PXH=1
export PX4_SIM_MODEL=gazebo-classic_iris
export VINS_WORLD=${VINS_WORLD:-vins_demo}
# Item #12: choose the mavros IMU rate per launch (default 50 Hz) so a
# high-rate experiment can never silently persist past its run.
export IMU_HZ=${IMU_HZ:-50}
# VINS writes its own scratch CSV (vins_result*.csv) to output_path; /data/results
# is the evidence tree, so scratch goes to /tmp instead of polluting it.
mkdir -p /tmp/vins_out
python3 /root/catkin_ws/src/vins_research/docker/set_imu_hz.py "$IMU_HZ" 2>&1 | tee -a /tmp/set_imu_hz.log
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:$LD_LIBRARY_PATH
/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_run.sh /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 none iris_fpv_cam "$VINS_WORLD" /root/PX4-Autopilot /root/PX4-Autopilot/build/px4_sitl_default