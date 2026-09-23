#!/bin/bash
source /root/catkin_ws/devel/setup.bash
source /opt/ros/noetic/setup.bash
pkill -9 -x gzserver 2>/dev/null; pkill -9 -x px4 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null; pkill -9 -f sitl_run.sh 2>/dev/null; sleep 2

# launch gzserver separately, capturing output
export GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib
export GAZEBO_MODEL_PATH=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic

xvfb-run -a -s '-screen 0 1920x1080x24' \
  timeout 60 gzserver --verbose \
  /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/empty.world \
  -s libgazebo_ros_api_plugin.so -s libgazebo_ros_paths_plugin.so \
  >/tmp/fresh12_gz.log 2>&1 &
sleep 10

echo "=== spawn model ==="
timeout 20 gz model --verbose --spawn-file=/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris_fpv_cam/iris_fpv_cam.sdf --model-name=iris_fpv_cam -x 1.01 -y 0.98 -z 0.83 2>&1 | head -5
sleep 5
echo "=== topics ==="
timeout 3 gz topic -l 2>/dev/null | grep -E 'mag|baro|imu|ground' | head
echo "=== mag hz ==="
timeout 5 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -2
echo "=== MAGDBG from gz log ==="
grep -a 'MAGDBG' /tmp/fresh12_gz.log | head -5
echo "=== GZ ERRORS ==="
grep -aE 'Failed|Err|error|Plugin' /tmp/fresh12_gz.log | grep -v 'display\|render\|X window\|XmlRpc\|ros_api\|ros_paths' | head -8

echo "=== now launch px4 ==="
export PX4_SIM_MODEL=gazebo-classic_iris
export NO_PXH=1
cd /root/PX4-Autopilot/build/px4_sitl_default/rootfs
timeout 20 /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 -d /root/PX4-Autopilot/build/px4_sitl_default/etc >/tmp/fresh12_px4.log 2>&1 &
sleep 15
echo "=== mag hz after px4 ==="
timeout 5 gz topic -z '/gazebo/default/iris_fpv_cam/mag' 2>&1 | head -2
echo "=== MAGDBG after px4 ==="
grep -a 'MAGDBG' /tmp/fresh12_gz.log | tail -5
echo "=== DONE ==="