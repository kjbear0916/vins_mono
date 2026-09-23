#!/bin/bash
set -u
echo "== include/SDF/Err lines =="
grep -aE 'include|SDF files|Unable|\[Err\]|\[Erm\]|model' /tmp/trial_tri.log | grep -avE 'modeling|gazebo/' | head -30
echo "== physics lines =="
grep -aiE 'physics' /tmp/trial_tri.log | head -8
echo "== entity/topic lines =="
grep -aE 'Created entity|spawning|Entities|entity' /tmp/trial_tri.log | head -10