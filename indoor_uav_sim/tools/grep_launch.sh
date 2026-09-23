#!/bin/bash
set +u
grep -nE 'connection_url|udpin|drone_control|connection' /workspace/disaster_drone_ws/src/drone_bringup/launch/full_system.launch.py