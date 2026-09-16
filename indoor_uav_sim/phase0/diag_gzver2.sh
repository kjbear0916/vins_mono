#!/usr/bin/env bash
set -u
RES=/tmp/gzver2.log
> "$RES"
pkill -9 -f 'gz sim' 2>/dev/null; pkill -9 -f 'gz-server' 2>/dev/null; sleep 1
timeout 9 gz sim -s -r /home/bear/PX4-Autopilot/Tools/simulation/gz/worlds/default.sdf >/dev/null 2>&1 &
sleep 6
echo "--- processes ---" >> "$RES"
ps -ef | grep -iE 'gz-(server|sim)|ruby3.0.*gz' | grep -v grep >> "$RES"
SPID=$(pgrep -f 'gz-server' | head -1)
if [ -n "$SPID" ]; then
  echo "server pid=$SPID exe=$(readlink /proc/$SPID/exe 2>/dev/null)" >> "$RES"
  echo "cmdline=$(tr '\0' ' ' < /proc/$SPID/cmdline)" >> "$RES"
fi
echo "--- done ---" >> "$RES"