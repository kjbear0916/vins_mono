#!/bin/bash
set +u
echo "== odometry plugin params (header) =="
grep -nE 'odom_frame|odom_tf_frame|topic|world_frame|update_rate|OdometryWithCovariance' /usr/share/gz/gz-sim8/system_plugins/odometry-publisher-system/README.md 2>/dev/null | head -20
ls /usr/share/gz/gz-sim8/system_plugins/odometry-publisher-system/ 2>/dev/null
echo "== try README =="
find / -path '*odometry-publisher*' -name 'README*' 2>/dev/null | head -3