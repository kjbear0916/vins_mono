#!/bin/bash
set +u
python3 /workspace/disaster_drone_ws/tools/patch_px4_model.py
grep -n 'odometry' /opt/PX4-Autopilot/Tools/simulation/gz/models/x500/model.sdf | head