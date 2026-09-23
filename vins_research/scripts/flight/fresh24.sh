#!/bin/bash
source /root/catkin_ws/devel/setup.bash
source /opt/ros/noetic/setup.bash
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4 2>/dev/null; sleep 2
if ! pgrep -x roscore >/dev/null 2>&1; then
  nohup roscore >/tmp/roscore.log 2>&1 &
  sleep 5
fi
export HEADLESS=1 NO_PXH=1 PX4_SIM_MODEL=gazebo-classic_iris DISPLAY=:0
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
timeout 60 gzserver --verbose \
  /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/empty.world \
  -s libgazebo_ros_api_plugin.so -s libgazebo_ros_paths_plugin.so \
  >/tmp/fresh24_gz.log 2>&1 &
GZPID=$!
sleep 12
for i in $(seq 1 10); do
  out=$(gz model --verbose --spawn-file=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris_fpv_cam/iris_fpv_cam.sdf --model-name=iris_fpv_cam -x 1.01 -y 0.98 -z 0.83 2>&1)
  if ! echo "$out" | grep -q "An instance of Gazebo is not running."; then echo "spawn OK iter=$i"; break; fi
  sleep 1
done
sleep 4
echo "=== baro echo 6s bytes ==="
timeout 7 gz topic -e '/gazebo/default/iris_fpv_cam/baro' 2>/tmp/fresh24_baro_echo.err >/tmp/fresh24_baro_echo.out
echo "stdout bytes: $(wc -c </tmp/fresh24_baro_echo.out)"
echo "stderr head:"; head -3 /tmp/fresh24_baro_echo.err
echo "stdout head:"; head -2 /tmp/fresh24_baro_echo.out
echo "=== mag for comparison ==="
timeout 3 gz topic -e '/gazebo/default/iris_fpv_cam/mag' 2>/dev/null | head -1
kill -9 $GZPID 2>/dev/null; sleep 1
echo DONE