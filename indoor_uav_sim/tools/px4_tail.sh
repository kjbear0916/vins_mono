#!/bin/bash
set +u
tr '\r' '\n' < /tmp/px4_sitl.log > /tmp/px4_wtf.log
echo "== last 30 meaningful lines =="
grep -avE '^pxh>|^\[2K|^$' /tmp/px4_wtf.log | tail -30
echo
echo "== any missing/warn in last 1000 lines =="
tail -1000 /tmp/px4_wtf.log | grep -aE 'WARN|missing|ekf2|failsafe|disarm|offboard' | tail -20