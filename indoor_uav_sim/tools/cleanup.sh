#!/bin/bash
set +u
truncate -s 0 /tmp/px4_sitl.log
kill -9 $(pgrep -f px4) $(pgrep -f gz) $(pgrep -f 'make px4') $(pgrep -f mavsdk_server) 2>/dev/null
sleep 3
ps aux | grep -E 'px4$|gz sim|make px4' | grep -v grep | wc -l
df -h /tmp | tail -1