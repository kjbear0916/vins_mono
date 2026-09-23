#!/bin/bash
echo "=== plugins in iris_fpv_cam.sdf ==="
grep -o 'filename="[^"]*"' /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris_fpv_cam/iris_fpv_cam.sdf
echo "=== sensor plugin libs present? ==="
for l in gazebo_imu_plugin gazebo_magnetometer_plugin gazebo_barometer_plugin gazebo_air_pressure_plugin gazebo_air_speed_plugin; do
  f=$(find /usr/lib/x86_64-linux-gnu/gazebo-11/plugins /root/PX4-Autopilot/build -name "$l.so" 2>/dev/null | head -1)
  echo "$l -> ${f:-MISSING}"
done
echo "=== does mavlink plugin need getsensor_imu? ==="
grep -c 'use_sensor_plugin\|sensor_imu' /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/src/mavlink_interface.cpp