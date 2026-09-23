#!/bin/bash
cd /root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
ninja libgazebo_barometer_plugin.so 2>&1 | tail -3
ls -la libgazebo_barometer_plugin.so
echo "updated:"
stat -c '%y' libgazebo_barometer_plugin.so