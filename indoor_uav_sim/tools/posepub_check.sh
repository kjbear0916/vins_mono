#!/bin/bash
set +u
ls /usr/lib/x86_64-linux-gnu/gz-sim-8/plugins/ | grep -iE 'pose|odom'
echo "== does PX4 model config reference pose publisher? =="
grep -rnE 'PosePublisher|pose-publisher|Odometry' /opt/PX4-Autopilot/Tools/simulation/gz/models/x500/model.sdf | head