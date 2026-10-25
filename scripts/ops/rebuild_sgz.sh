#!/bin/bash
cd /root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
make -j$(nproc) 2>&1 | tail -30
echo "=== rebuild done ==="
ls -la libgazebo_imu_plugin.so libgazebo_magnetometer_plugin.so libgazebo_barometer_plugin.so libgazebo_mavlink_interface.so libgazebo_groundtruth_plugin.so