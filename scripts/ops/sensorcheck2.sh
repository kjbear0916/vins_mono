#!/bin/bash
echo "=== required model plugins: existence ==="
for l in libgazebo_barometer_plugin.so libgazebo_groundtruth_plugin.so libgazebo_imu_plugin.so libgazebo_magnetometer_plugin.so libgazebo_mavlink_interface.so libgazebo_motor_model.so libgazebo_multirotor_base_plugin.so; do
  f=$(find /usr/lib/x86_64-linux-gnu/gazebo-11/plugins /root/PX4-Autopilot/build -name "$l" 2>/dev/null | head -1)
  echo "$l -> ${f:-MISSING}"
done
echo "=== what gzserver actually loaded (plugin libs from log) ==="
grep -aiE 'load.*(imu|mag|baro|motor|mavlink|multirotor|groundtruth)' /tmp/fresh3_sim.log | head -12