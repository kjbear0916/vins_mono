#!/bin/bash
# Detached, resumable EuRoC-direction bag fetch for VINS-Mono.
# room1 (TUM-VI) — the sequence the shipped tum_config.yaml points at.
# wget -c : survives docker daemon flapping (the sim killer) mid-download.
cd /root/euroc || mkdir -p /root/euroc && cd /root/euroc

BAG="dataset-room1_512_16.bag"
URL="https://cvg.cit.tum.de/_media/data/datasets/visual-inertial-dataset/$BAG"

echo "==BAG_START=$(date -u +%H:%M:%S) url=$URL" > /tmp/room1dl.pid
nohup bash -c "
  wget -c -q -O '$BAG' '$URL'
  echo \"BAG_EXIT=\$? at \$(date -u +%H:%M:%S)\" >> /tmp/room1dl.pid
  echo \"BAG_BYTES=\$(stat -c%s '$BAG' 2>/dev/null)\" >> /tmp/room1dl.pid
" >> /tmp/room1dl.log 2>&1 &
echo "DL_PID=$!" >> /tmp/room1dl.pid

echo "==ROOM1_DL_LAUNCHED==" 
cat /tmp/room1dl.pid
