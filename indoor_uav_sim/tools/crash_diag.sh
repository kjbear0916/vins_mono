#!/bin/bash
set +u
echo "== waypoint_navigator crash =="
grep -aA25 -E 'waypoint_navigator.*Traceback' /tmp/full_system3.log | head -35
echo
echo "== mission_planner crash =="
grep -aA25 -E 'mission_planner.*Traceback' /tmp/full_system3.log | head -35