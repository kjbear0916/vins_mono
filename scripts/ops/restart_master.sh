#!/bin/bash
set -x
pkill -9 -x mavros_node 2>/dev/null
MPID=$(ps -eo pid,args | grep -F 'opt/ros/noetic/bin/rosmaster' | grep -v grep | awk '{print $1}')
CPID=$(ps -eo pid,args | grep -F 'opt/ros/noetic/bin/roscore' | grep -v grep | awk '{print $1}')
[ -n "$MPID" ] && kill -9 "$MPID"
[ -n "$CPID" ] && kill -9 "$CPID"
sleep 3
ps -eo pid,args | grep -F 'opt/ros/noetic/bin/ros' | grep -v grep | wc -l
echo KILLDONE