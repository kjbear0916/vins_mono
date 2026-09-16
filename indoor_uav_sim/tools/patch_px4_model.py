#!/usr/bin/env python3
"""
Inject nadir camera / front camera / 2D lidar sensors into the PX4 x500
model used by Gazebo SITL.

PX4 ships its SITL drone model at:
    Tools/simulation/gz/models/x500/model.sdf
The stock model carries no downward/flight RGB cameras or lidar; this
script adds three sensors + fixed joints to the base link so the ROS2
perception layer has something to consume (spec section 5.5).

Idempotent: guarded by a marker comment, safe to run repeatedly.

Topic naming (gz transport):
  sensor_nadir/image  -> bridged to /drone/camera/nadir/image_raw
  sensor_front/image  -> bridged to /drone/camera/front/image_raw
  sensor_lidar/scan   -> bridged to /drone/lidar/scan
See src/drone_bringup/config/ros_bridge.yaml for the ros_gz bridge map.

Run inside the container (paths default to the PX4 checkout):
    python3 /workspace/disaster_drone_ws/tools/patch_px4_model.py
"""
import argparse
from pathlib import Path

MARKER = "<!-- disaster-drone sensors (patch_px4_model.py) -->"

SENSORS_XML = """
  <!-- disaster-drone sensors (patch_px4_model.py) -->
  <link name="sensor_rig">
    <pose>0 0 0.1 0 0 0</pose>
    <inertial>
      <mass>0.05</mass>
      <inertia>
        <ixx>0.0001</ixx><iyy>0.0001</iyy><izz>0.0001</izz>
        <ixy>0</ixy><ixz>0</ixz><iyz>0</iyz>
      </inertia>
    </inertial>
  </link>
  <joint name="sensor_rig_fixed" type="fixed">
    <parent>base_link</parent>
    <child>sensor_rig</child>
  </joint>

  <link name="sensor_nadir_mount">
    <pose>0 0 -0.05 0 0 0</pose>
    <inertial>
      <mass>0.01</mass>
      <inertia><ixx>0.0001</ixx><iyy>0.0001</iyy><izz>0.0001</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia>
    </inertial>
    <sensor type="camera" name="sensor_nadir">
      <pose>0 0 0 3.14159 0 0</pose>
      <topic>sensor_nadir/image</topic>
      <update_rate>15</update_rate>
      <camera>
        <horizontal_fov>1.3963</horizontal_fov>
        <image><width>640</width><height>480</height></image>
        <clip><near>0.1</near><far>50</far></clip>
      </camera>
    </sensor>
  </link>
  <joint name="sensor_nadir_fixed" type="fixed">
    <parent>sensor_rig</parent>
    <child>sensor_nadir_mount</child>
  </joint>

  <link name="sensor_front_mount">
    <pose>0.15 0 0 0 0 0</pose>
    <inertial>
      <mass>0.01</mass>
      <inertia><ixx>0.0001</ixx><iyy>0.0001</iyy><izz>0.0001</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia>
    </inertial>
    <sensor type="camera" name="sensor_front">
      <pose>0 0 0 0 0 0</pose>
      <topic>sensor_front/image</topic>
      <update_rate>15</update_rate>
      <camera>
        <horizontal_fov>1.3963</horizontal_fov>
        <image><width>640</width><height>480</height></image>
        <clip><near>0.1</near><far>50</far></clip>
      </camera>
    </sensor>
  </link>
  <joint name="sensor_front_fixed" type="fixed">
    <parent>sensor_rig</parent>
    <child>sensor_front_mount</child>
  </joint>

  <link name="sensor_lidar_mount">
    <pose>0.08 0 0 0 0 0</pose>
    <inertial>
      <mass>0.01</mass>
      <inertia><ixx>0.0001</ixx><iyy>0.0001</iyy><izz>0.0001</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia>
    </inertial>
    <sensor type="gpu_lidar" name="sensor_lidar">
      <pose>0 0 0 0 0 0</pose>
      <topic>sensor_lidar/scan</topic>
      <update_rate>20</update_rate>
      <lidar>
        <scan><horizontal><samples>360</samples><resolution>1</resolution><min_angle>-3.14159</min_angle><max_angle>3.14159</max_angle></horizontal></scan>
        <range><min>0.3</min><max>25.0</max></range>
      </lidar>
    </sensor>
  </link>
  <joint name="sensor_lidar_fixed" type="fixed">
    <parent>sensor_rig</parent>
    <child>sensor_lidar_mount</child>
  </joint>
"""


def patch(model_sdf: Path) -> bool:
    if not model_sdf.exists():
        raise FileNotFoundError(model_sdf)
    text = model_sdf.read_text(encoding="utf-8")
    if MARKER in text:
        print("already patched; no change")
        return False

    close = "</model>"
    if close not in text:
        raise ValueError(f"{model_sdf}: no </model> found")
    idx = text.rindex(close)
    text = text[:idx] + SENSORS_XML + "\n" + text[idx:]
    model_sdf.write_text(text, encoding="utf-8")
    print(f"patched {model_sdf}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Inject RGB/lidar sensors into the PX4 x500 SITL model")
    ap.add_argument("model",
                    nargs="?",
                    default="/opt/PX4-Autopilot/Tools/simulation/gz/models/x500/model.sdf")
    args = ap.parse_args()
    patch(Path(args.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())