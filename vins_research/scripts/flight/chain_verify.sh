#!/bin/bash
source /root/catkin_ws/devel/setup.bash
source /opt/ros/noetic/setup.bash
# fresh full chain
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null
sleep 2
nohup bash /root/sim_launch.sh >/tmp/fresh7_sim.log 2>&1 &
echo "chain started, waiting 25s"
sleep 25
echo "=== HIL_SENSOR check from px4 log ==="
grep -aE 'EKF|ekf|sensor|IMU|imu|hrt|att|preflight|arming|MAV' /tmp/fresh7_sim.log | head -15
echo
echo "=== imu topic Hz (5s) ==="
timeout 6 gz topic -z '/gazebo/default/iris_fpv_cam/imu' 2>&1 | head -2
echo "=== run ekf_probe ==="
python3 -u /tmp/ekf_probe.py 2>&1 | head -40
echo "=== done ==="