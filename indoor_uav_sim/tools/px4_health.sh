#!/bin/bash
set +u
sleep 20
tr '\r' '\n' < /tmp/px4_sitl.log > /tmp/px4_now.log
echo "== recent sensor/ekf/commander =="
grep -aE 'sensor|ekf|commander|GPS|navsat|EKF|vehicle_status|consistent|controller|Preflight|arm' /tmp/px4_now.log | tail -25
echo
echo "== last non-pxh lines =="
grep -avE '^pxh>|^$' /tmp/px4_now.log | tail -15