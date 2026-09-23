#!/usr/bin/env python3
"""Patch marker models: add model.config if missing."""
import glob
from pathlib import Path

for d in glob.glob("/workspace/disaster_drone_ws/src/drone_bringup/models/marker_*/"):
    mid = Path(d).name
    cfg = Path(d) / "model.config"
    if cfg.exists():
        continue
    cfg.write_text(
        '<?xml version="1.0" ?>\n'
        "<model>\n"
        f"  <name>{mid}</name>\n"
        '  <sdf version="1.9">model.sdf</sdf>\n'
        "</model>\n"
    )
print(f"patched {len(glob.glob('/workspace/disaster_drone_ws/src/drone_bringup/models/marker_*/model.config'))} marker models")
