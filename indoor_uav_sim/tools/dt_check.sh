#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
echo "== hz camera nadir =="
timeout 6 ros2 topic hz /drone/camera/nadir/image_raw 2>&1 | head -4 &
sleep 7
echo "== hz laser =="
timeout 6 ros2 topic hz /drone/lidar/scan 2>&1 | head -4
echo "== hz fused pose =="
timeout 6 ros2 topic hz /drone/pose/fused 2>&1 | head -4
echo "== fused sample =="
timeout 3 ros2 topic echo /drone/pose/fused 2>&1 | head -20