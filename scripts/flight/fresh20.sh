#!/bin/bash
source /root/catkin_ws/devel/setup.bash
source /opt/ros/noetic/setup.bash
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null; pkill -9 -f sitl_run.sh 2>/dev/null; sleep 2
if ! pgrep -x roscore >/dev/null 2>&1; then
  nohup roscore >/tmp/roscore.log 2>&1 &
  sleep 5
fi
export HEADLESS=1
export NO_PXH=1
export PX4_SIM_MODEL=gazebo-classic_iris
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
# === replicate sitl_run.sh but WITHOUT xvfb-run, gzserver stderr to file ===
export DISPLAY=:0
echo "=== 1. gzserver (no xvfb) ==="
timeout 100 gzserver --verbose \
  /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/empty.world \
  -s libgazebo_ros_api_plugin.so -s libgazebo_ros_paths_plugin.so \
  >/tmp/fresh20_gz.log 2>&1 &
GZPID=$!
sleep 12
echo "=== 2. spawn model (loop until ready like sitl_run) ==="
for i in $(seq 1 15); do
  out=$(gz model --verbose --spawn-file=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris_fpv_cam/iris_fpv_cam.sdf --model-name=iris_fpv_cam -x 1.01 -y 0.98 -z 0.83 2>&1)
  if ! echo "$out" | grep -q "An instance of Gazebo is not running."; then echo "spawn OK iter=$i"; break; fi
  echo "retry $i"; sleep 1
done
sleep 5
echo "=== 3. px4 ==="
cd /root/PX4-Autopilot/build/px4_sitl_default/rootfs
timeout 80 /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 -d /root/PX4-Autopilot/build/px4_sitl_default/etc >/tmp/fresh20_px4.log 2>&1 &
PX4_PID=$!
sleep 20
echo "=== px4 conn status ==="
grep -aE 'Simulator connected|lockstep|Waiting for simulator' /tmp/fresh20_px4.log | head -4
echo "=== imu hz ==="
timeout 5 gz topic -z '/gazebo/default/iris_fpv_cam/imu' 2>&1 | head -2
echo "=== mag hz ==="
timeout 5 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -2
echo "=== baro hz ==="
timeout 5 gz topic -z '/gazebo/default/iris_fpv_cam/baro' 2>&1 | head -2
echo "=== MAGDBG ==="
grep -a 'MAGDBG' /tmp/fresh20_gz.log | head -5
echo "=== gz err ==="
grep -aE 'Err' /tmp/fresh20_gz.log | grep -v 'display\|XmlRpc\|write error\|couldn.t\|RosApi\|CameraSensor' | head -4
kill -9 $GZPID $PX4_PID 2>/dev/null; sleep 1
echo DONE