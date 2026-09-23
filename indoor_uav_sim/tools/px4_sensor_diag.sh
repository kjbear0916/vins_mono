#!/bin/bash
set +u
tr '\r' '\n' < /tmp/px4_sitl.log > /tmp/px4_clean.log
echo "== sensor/bridge related =="
grep -aE 'sensor|imu|baro|mag|navsat|gz_bridge|gz.*subscribe|Waiting for uorb|sensor_gz|Simulator' /tmp/px4_clean.log | grep -avE 'model inspection|servo_' | tail -30
echo
echo "== uorb sensor instances =="
grep -aE 'listed|publishing|subscribed' /tmp/px4_clean.log | tail -20
echo
echo "== any errors =="
grep -aE 'ERROR|FAILED|emergency' /tmp/px4_clean.log | tail -10