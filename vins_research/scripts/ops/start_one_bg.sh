#!/bin/bash
cd /tmp
nohup bash /tmp/trial_one.sh high circle 1.5 5.0 3.0 45 1 > /tmp/trial_wrap.log 2>&1 &
echo "STARTED_PID=$!"
