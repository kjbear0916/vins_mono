#!/bin/bash
L=/tmp/ethzprobe.log
: > "$L"
echo "==ETHZ_CANONICAL_HOST_443==" >> "$L"
timeout 20 bash -c 'exec 3<>/dev/tcp/projects.asl.ethz.ch/443 && echo TCP_OPEN || echo TCP_FAIL' >> "$L" 2>&1
echo "==ETHZ_CANONICAL_HEAD==" >> "$L"
timeout 25 curl -sIL --max-redirs 3 "https://projects.asl.ethz.ch/datasets/doku.php?id=kmavvisualinertialdatasets" >> "$L" 2>&1
echo "==ETHZ_BAG_HTTPS301==" >> "$L"
timeout 25 curl -sIL "https://projects.asl.ethz.ch/datasets/data/..." >> "$L" 2>&1
echo "==ROBOTICS_443_RETRY==" >> "$L"
timeout 15 bash -c 'exec 3<>/dev/tcp/robotics.ethz.ch/443 && echo TCP_OPEN || echo TCP_FAIL' >> "$L" 2>&1
echo "==ROBOTICS_HTTP_80==" >> "$L"
timeout 15 bash -c 'exec 3<>/dev/tcp/robotics.ethz.ch/80 && echo TCP_OPEN_80 || echo TCP_FAIL_80' >> "$L" 2>&1
echo ==START=$(date -u +%H:%M:%S)== >> "$L"
echo ==DIAG_DONE== >> "$L"
cat "$L"
