#!/bin/bash
L=/tmp/room1chain.log; : > "$L"
echo "==S=$(date -u +%H:%M:%S)==" >> "$L"
echo "==ROOM1_EST_FINAL_LOC2==" >> "$L"
timeout 30 bash -c 'exec 3<>/dev/tcp; ' 2>/dev/null
# follow the 302 chain to its end with curl -L, capture final effective URL
timeout 60 curl -sL -o /dev/null -w "FINAL_URL=%{url_effective}\nHTTP=%{http_code}\n" \
  "http://vision.in.tum.de/tumvi/calibrated/512_16/dataset-room1_512_16.bag" 2>&1 >> "$L" 2>&1
echo "==END=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
