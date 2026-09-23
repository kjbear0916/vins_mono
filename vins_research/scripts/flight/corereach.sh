#!/bin/bash
# Sole purpose: answer "can the container reach the public internet at all, right now?"
# No pipes, no $(), no &&/|| in the ORCHESTRATOR layer. All logic inside this file.
L=/tmp/corereach.log
: > "$L"
echo "==T0_UTC=$(date -u +%H:%M:%S)==" >> "$L"
echo "==DOCKER_ENGINE_TICKS==" >> "$L"
ps -eo pid,etimes,cmd | grep -E "com.docker|dockerd" | grep -v grep >> "$L"
echo "==OPEN_FILES_OVERTIME==" >> "$L"
docker info 2>&1 | grep -iE "Server Version|ERROR|Cannot" >> "$L"
echo "==TCP_443_ETHZ==" >> "$L"
timeout 18 bash -c 'exec 3<>/dev/tcp/robotics.ethz.ch/443 && echo TCP443_OPEN || echo TCP443_CLOSED' >> "$L" 2>&1
echo "==TCP_443_GITHUB==" >> "$L"
timeout 18 bash -c 'exec 3<>/dev/tcp/github.com/443 && echo TCP443_GH_OPEN || echo TCP443_GH_CLOSED' >> "$L" 2>&1
echo "==DNS==" >> "$L"
getent hosts robotics.ethz.ch >> "$L"
getent hosts github.com >> "$L"
echo "==CURL_LEXFUSION==" >> "$L"
timeout 20 curl -sIL "https://projects.asl.ethz.ch/datasets/doku.php" 2>&1 | head -6 >> "$L"
echo "==END=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
