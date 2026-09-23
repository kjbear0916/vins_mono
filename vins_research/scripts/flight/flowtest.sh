#!/bin/bash
# Decisive: did ANY EuRoC bag bytes actually flow in this container?
# Tests the 3 candidate hosts with wget -c (resume, 25s cap each WINDOW),
# prints EXACT bytes-received, NOT guessed headers. No guessing.
L=/tmp/flowtest.log; : > "$L"
echo "==START=$(date -u +%H:%M:%S)==" >> "$L"

# wget --spider gives SERVER-RESPONSE (redirect chain), wget fallback shows
# whether ANY bytes got written. Both verdicts written to $L, never piped.
for spec in \
  "ETHZ_CLASSIC_HTTP|http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/machine_hall/MH_01_easy/MH_01_easy.bag" \
  "ETHZ_CLASSIC_HTTPS|https://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/machine_hall/MH_01_easy/MH_01_easy.bag" \
  "ETHZ_CLASSIC_HTTPS_W3|https://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/machine_hall/MH_01_easy/MH_01_easy.bag" \
  "ASL_GH_MIRROR|https://github.com/ethz-asl/vins-mono" \
; do
  name=${spec%%|*}; url=${spec#*|}
  echo "### $name ###" >> "$L"
  echo "--spider--" >> "$L"
  timeout 15 wget -q --spider --server-response "$url" 2>&1 | grep -iE "HTTP/|Location|Content-Length|Read error" >> "$L"
  echo "--fetch-bytes--" >> "$L"
  rm -f /tmp/flow_probe 2>/dev/null
  timeout 15 wget -q -T 10 -O /tmp/flow_probe "$url" 2>/dev/null
  s=0; [ -f /tmp/flow_probe ] && s=$(stat -c%s /tmp/flow_probe 2>/dev/null)
  echo "fetched_bytes=$s" >> "$L"
  rm -f /tmp/flow_probe
done

echo "==END=$(date -u +%H:%M:%S)==" >> "$L"
cat "$L"
