#!/bin/bash
set +u
echo "== drone_control log =="
grep -a 'drone_control' /tmp/full_system4.log | tail -20
echo
echo "== full_system4 any INFO from all nodes (recent) =="
grep -aE 'INFO.*(drone_control|mission_planner|waypoint_navigator|anchor_manager)' /tmp/full_system4.log | tail -15
echo
echo "== px4 recent (roll the cursor spam away) =="
tr '\r' '\n' < /tmp/px4_sitl.log | grep -avE '^pxh>' | grep -aE 'INFO|WARN|ERROR' | tail -30