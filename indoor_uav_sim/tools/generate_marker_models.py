#!/usr/bin/env python3
"""
Generate ArUco marker model directories for the Gazebo disaster building.

For each marker id in the ids list, creates:
  models/markers/marker_<id>/
    model.sdf                     (thin 0.5x0.5m box, PBR albedo = texture)
    materials/textures/marker_<id>.png   (minimal border + bit grid)

Dictionary: DICT_7X7_1000 (ids 0..999) — matches marker_map.yaml scheme
where semantic id = floor*100 + room*10 + wp.

Run on host (needs opencv-contrib) OR inside the container:
    python3 tools/generate_marker_models.py
"""
import os
import sys

import cv2

try:
    import cv2.aruco as aruco
except ImportError:  # opencv 4.7+
    import cv2.aruco as aruco  # noqa: F401
try:
    import yaml
except ImportError:
    yaml = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Gazebo resolves model://marker_<id> as <resource>/models/marker_<id>/model.sdf,
# so each marker gets its own model dir directly under models/.
OUT_DIR = os.path.join(ROOT, "src", "drone_bringup", "models")
MARKER_MAP = os.path.join(ROOT, "src", "drone_bringup", "config", "marker_map.yaml")

MARKER_MM = 500       # physical marker size in mm (sim).
PX_PER_MARKER = 256   # texture pixel resolution per marker
BORDER_BITS = 1       # standard aruco black border width (bits)
DICT_ID = cv2.aruco.DICT_7X7_1000 if hasattr(cv2.aruco, "DICT_7X7_1000") else getattr(
    cv2.aruco, "DICT_7X7_1000", None)


def marker_ids_to_generate():
    """Marker ids come straight from marker_map.yaml (single source of truth)."""
    if yaml is None:
        raise SystemExit("PyYAML required to read marker_map.yaml")
    with open(MARKER_MAP, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    ids = sorted(int(mid) for mid in data["markers"].keys())
    # survivors are included in the map; nothing extra needed
    return ids


def render_marker(dict_, marker_id, px, border_bits):
    """Render an aruco marker image with border, returns 0..255 uint8."""
    img = aruco.generateImageMarker(
        dict_, marker_id, sidePixels=px, borderBits=border_bits)
    return img


def write_model_sdf(marker_id):
    """Thin visual-only box with PBR albedo texture."""
    return f"""<?xml version="1.0"?>
<sdf version="1.9">
  <model name="marker_{marker_id}">
    <static>true</static>
    <link name="marker">
      <visual name="visual">
        <pose>0 0 0 0 0 0</pose>
        <geometry>
          <box><size>0.5 0.5 0.005</size></box>
        </geometry>
        <material>
          <pbr>
            <metal>
              <albedo_map>materials/textures/marker_{marker_id}.png</albedo_map>
            </metal>
          </pbr>
        </material>
      </visual>
    </link>
  </model>
</sdf>
"""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    dictionary = aruco.getPredefinedDictionary(DICT_ID)
    ids = marker_ids_to_generate()
    print(f"Generating {len(ids)} markers into {OUT_DIR}")
    for mid in ids:
        d = os.path.join(OUT_DIR, f"marker_{mid}")
        tex_dir = os.path.join(d, "materials", "textures")
        os.makedirs(tex_dir, exist_ok=True)
        img = render_marker(dictionary, mid, PX_PER_MARKER, BORDER_BITS)
        out_png = os.path.join(tex_dir, f"marker_{mid}.png")
        cv2.imwrite(out_png, img)
        with open(os.path.join(d, "model.sdf"), "w", encoding="utf-8") as f:
            f.write(write_model_sdf(mid))
        print(f"  marker_{mid} -> {out_png}")
    print("Done. models/markers has a model dir + texture per marker.")


if __name__ == "__main__":
    sys.exit(main())