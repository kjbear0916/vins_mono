#!/bin/bash
source /opt/ros/noetic/setup.bash
for bag in /data/rosbags/*.bag; do
    printf "%s: " "$bag"
    if rosbag info "$bag" > /dev/null 2>&1; then
        echo "OK"
    else
        echo "UNINDEXED"
    fi
done
