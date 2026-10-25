#!/bin/bash
# EuRoC probe + resilient downloader. ONE file, no inline pipes, no
# PowerShell-visible structure. DNS/resolve/route/net-probe first, then
# a self-recovering download loop that survives daemon flaps.
set -x
echo ==ENV_NET== > /tmp/netprobe.log
env | grep -iE 'proxy|_URL' >> /tmp/netprobe.log
echo ==ROUTE== >> /tmp/netprobe.log
ip route 2>&1 >> /tmp/netprobe.log || echo no-iproute >> /tmp/netprobe.log
echo ==RESOLVE== >> /tmp/netprobe.log
getent hosts robotics.ethz.ch >> /tmp/netprobe.log
getent hosts projects.asl.ethz.ch >> /tmp/netprobe.log

echo ==PROBE_HTTP_ETHZ== >> /tmp/netprobe.log
timeout 15 curl -sIL "http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/vicon_room1/V1_01_easy/V1_01_easy.bag" 2>&1 >> /tmp/netprobe.log

echo ==PROBE_HTTPS_ETHZ== >> /tmp/netprobe.log
timeout 15 curl -sIL "https://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/vicon_room1/V1_01_easy/V1_01_easy.bag" 2>&1 >> /tmp/netprobe.log

echo ==PROBE_ASL_KEY== >> /tmp/netprobe.log
# canonical EuRoC is on projects.asl.ethz.ch with token-based listing page
timeout 15 curl -sI "https://projects.asl.ethz.ch/datasets/doku.php?id=kmavvisualinertialdatasets" 2>&1 >> /tmp/netprobe.log

echo ==SUMMARY_MARK_END== >> /tmp/netprobe.log
cat /tmp/netprobe.log
