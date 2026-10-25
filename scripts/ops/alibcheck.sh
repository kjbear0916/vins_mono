#!/bin/bash
echo "=== ALL installs of the sensor/mavlink plugin libs ==="
for l in libgazebo_imu_plugin libgazebo_magnetometer_plugin libgazebo_barometer_plugin libgazebo_groundtruth_plugin libgazebo_motor_model libgazebo_mavlink_interface; do
  echo "--- $l ---"
  find / -name "$l.so" 2>/dev/null | head -5
done
echo
echo "=== ldd: any unresolved deps? ==="
ldd /root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic/libgazebo_imu_plugin.so 2>&1 | grep -i 'not found'
ldd /root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic/libgazebo_magnetometer_plugin.so 2>&1 | grep -i 'not found'
ldd /root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic/libgazebo_mavlink_interface.so 2>&1 | grep -i 'not found'
echo "(empty above = all deps resolve)"
echo
echo "=== submodule CMakeLists diff (the only dirty file) ==="
cd /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic
git diff CMakeLists.txt | head -40