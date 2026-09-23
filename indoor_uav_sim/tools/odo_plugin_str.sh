#!/bin/bash
set +u
echo "== strings in odometry plugin =="
strings /usr/lib/x86_64-linux-gnu/gz-sim-8/plugins/libgz-sim8-odometry-publisher-system.so | grep -iE 'odom|frame|topic|frequency|publish' | grep -v '^_' | sort -u | head -30