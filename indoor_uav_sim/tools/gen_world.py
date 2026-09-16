#!/usr/bin/env python3
"""
Generate the multi-floor disaster building world SDF for Gazebo Harmonic.

Single source of truth: src/drone_bringup/config/marker_map.yaml
  - every marker in the map is <include>d into the world at its pose
  - marker z is a *floor-mounted* pose (matches the nadir camera, spec
    section 5.5): z = floor walking surface + 0.05

Structure (SPEC.md section 5):
  - 3 floors, 3 m storey height, footprint 20 x 10 m
  - corridor along y=-1, room strip south of a partition wall (y=-2.8)
    with three door gaps; rooms A (west), open (center), B (east)
  - open stairwell/atrium shaft x in [-8,-6], y in [-4,0]; floors 2/3
    slabs are built from 4 boxes around the opening so the drone climbs
    vertically through the atrium
  - stairwell markers are floor-mounted: 109 sits on the solid F1 slab
    at the shaft centre; 209/309 sit just east of the shaft opening so a
    nadir camera can re-acquire ArUco after the vertical climb

Usage:
    python3 tools/gen_world.py [--occlude ID] [--out PATH]

Run tools/generate_marker_models.py first so the `model://marker_<id>`
includes resolve.
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "src" / "drone_bringup" / "worlds"
MARKER_MAP = ROOT / "src" / "drone_bringup" / "config" / "marker_map.yaml"
WORLD_NAME = "three_floor_building"

# --- building geometry -------------------------------------------------------
SX, SY = 10.0, 5.0          # footprint half extents
SLAB_THICK = 0.2
STOREY = 3.0
SHAFT = {"x0": -8.0, "x1": -6.0, "y0": -4.0, "y1": 0.0}
WALL_THICK = 0.2
WALL_HEIGHT = 2.8
MARKER_CLEAR = 0.05         # marker datum above walking surface
PLYWOOD = {"ambient": (0.62, 0.58, 0.5, 1.0), "diffuse": (0.72, 0.68, 0.6, 1.0)}
WALL_MAT = {"ambient": (0.8, 0.8, 0.75, 1.0), "diffuse": (0.85, 0.85, 0.8, 1.0)}


def surface_z(floor: int) -> float:
    """Top of the slab (walking surface) for floor 1..3."""
    return (floor - 1) * STOREY + SLAB_THICK


def mat(tag: str, color: dict) -> str:
    if tag == "visual":
        amb = color["ambient"]
        dif = color["diffuse"]
        return (
            f"            <material>\n"
            f"              <ambient>{amb[0]} {amb[1]} {amb[2]} {amb[3]}</ambient>\n"
            f"              <diffuse>{dif[0]} {dif[1]} {dif[2]} {dif[3]}</diffuse>\n"
            f"            </material>\n"
        )
    return ""


def box_model(name: str, cx: float, cy: float, cz: float,
              lx: float, ly: float, lz: float, color: tuple) -> str:
    """Static single-link box with visual + collision."""
    return f"""\
  <model name="{name}">
    <static>true</static>
    <pose>{cx} {cy} {cz} 0 0 0</pose>
    <link name="link">
      <visual name="visual">
        <geometry>
          <box><size>{lx} {ly} {lz}</size></box>
        </geometry>
{mat('visual', color)}
      </visual>
      <collision name="collision">
        <geometry>
          <box><size>{lx} {ly} {lz}</size></box>
        </geometry>
      </collision>
    </link>
  </model>
"""


def floor_slabs(floor: int) -> list[str]:
    """Slab boxes for a floor: full on F1, 4 pieces around shaft on F2/F3."""
    cz = surface_z(floor) - SLAB_THICK / 2.0
    if floor == 1:
        slabs = [{"name": f"f{floor}_slab", "cx": 0.0, "cy": 0.0,
                  "lx": 2 * SX, "ly": 2 * SY, "lz": SLAB_THICK}]
    else:
        x0, x1, y0, y1 = SHAFT["x0"], SHAFT["x1"], SHAFT["y0"], SHAFT["y1"]
        slabs = [
            {"name": f"f{floor}_slab_w", "cx": (-SX + x0) / 2, "cy": 0.0,
             "lx": x0 + SX, "ly": 2 * SY, "lz": SLAB_THICK},
            {"name": f"f{floor}_slab_e", "cx": (x1 + SX) / 2, "cy": 0.0,
             "lx": SX - x1, "ly": 2 * SY, "lz": SLAB_THICK},
            {"name": f"f{floor}_slab_n", "cx": (x0 + x1) / 2, "cy": (-SY + y0) / 2,
             "lx": x1 - x0, "ly": y0 + SY, "lz": SLAB_THICK},
            {"name": f"f{floor}_slab_s", "cx": (x0 + x1) / 2, "cy": (y1 + SY) / 2,
             "lx": x1 - x0, "ly": SY - y1, "lz": SLAB_THICK},
        ]
    return [box_model(s.pop("name"), s["cx"], s["cy"], cz, s["lx"], s["ly"], s["lz"],
                      PLYWOOD) for s in slabs]


def partition_walls(floor: int) -> list[str]:
    """Corridor/room partition along y=-2.8 with three door gaps.

    On F2/F3 the west segment stops at the shaft edge x=-8 so it never
    blocks the atrium opening. Doors at x [-5,-4], [-1,1], [4,5].
    """
    cy = -2.8
    cz = surface_z(floor) + WALL_HEIGHT / 2.0
    segs = [(-10.0, -5.0), (-4.0, -1.0), (1.0, 4.0), (5.0, 10.0)]
    models = []
    for i, (a, b) in enumerate(segs):
        if floor > 1 and a < SHAFT["x0"] and b > SHAFT["x0"]:
            b = SHAFT["x0"]                       # keep west of the atrium
        if b - a < 0.05:
            continue
        cx = (a + b) / 2.0
        models.append(box_model(f"f{floor}_part_w{i+1}", cx, cy, cz,
                                b - a, WALL_THICK, WALL_HEIGHT, WALL_MAT))
    return models


def perimeter_walls(floor: int) -> list[str]:
    models = []
    cz = surface_z(floor) + WALL_HEIGHT / 2.0
    spec = [
        ("n", 0.0, -SY - WALL_THICK / 2.0, 2 * SX, WALL_THICK),
        ("s", 0.0, SY + WALL_THICK / 2.0, 2 * SX, WALL_THICK),
        ("w", -SX - WALL_THICK / 2.0, 0.0, WALL_THICK, 2 * SY),
        ("e", SX + WALL_THICK / 2.0, 0.0, WALL_THICK, 2 * SY),
    ]
    for tag, cx, cy, lx, ly in spec:
        models.append(box_model(f"f{floor}_wall_{tag}", cx, cy, cz, lx, ly,
                                WALL_HEIGHT, WALL_MAT))
    return models


def light(floor: int) -> str:
    """Point light inside each storey."""
    cz = surface_z(floor) + WALL_HEIGHT - 0.1
    return f"""\
  <light type="point" name="pt_{floor}F">
    <pose>0 0 {cz:.1f} 0 0 0</pose>
    <diffuse>0.75 0.75 0.7 1</diffuse>
    <specular>0.15 0.15 0.15 1</specular>
    <attenuation>
      <range>14</range>
      <constant>0.9</constant>
      <linear>0.06</linear>
      <quadratic>0.01</quadratic>
    </attenuation>
  </light>
"""


def marker_includes(markers: dict, occlude: int | None) -> list[str]:
    """Include each marker model at its map pose.

    Pose is the floor-mount: roll/pitch 0, yaw from the map. Marker z from
    the map is already the floor-mounted datum.
    """
    blocks = []
    for mid, pose in sorted(markers.items()):
        uri = f"model://marker_{mid}"
        blocks.append(f"""\
  <include>
    <uri>{uri}</uri>
    <pose>{pose['x']} {pose['y']} {pose['z']} 0 0 {pose.get('yaw', 0.0)}</pose>
  </include>
""")
        if occlude is not None and mid == occlude:
            blocks.append(box_model(
                f"occluder_{mid}", pose['x'], pose['y'], pose['z'] + 0.02,
                1.0, 1.0, 0.02, (0.05, 0.05, 0.05, 1.0)))
    return blocks


def build_world(markers: dict, occlude: int | None) -> str:
    lighting = "".join(light(f) for f in (1, 2, 3))
    slabs = "".join(slabs for f in (1, 2, 3) for slabs in floor_slabs(f))
    walls = "".join(w for f in (1, 2, 3) for w in perimeter_walls(f) + partition_walls(f))
    markers_xml = "".join(marker_includes(markers, occlude))

    return f"""<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="{WORLD_NAME}">

    <plugin filename="gz-sim-physics" name="gz::sim::systems::Physics">
      <gravity>0 0 -9.8</gravity>
    </plugin>
    <plugin filename="gz-sim-user-commands" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-contact-system" name="gz::sim::systems::Contact"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>

    <gui fullscreen="0">
      <plugin filename="gz-sim-scene-3d" name="gz::sim::systems::Scene3D"/>
      <plugin filename="gz-sim-follow" name="gz::sim::systems::Follow">
        <target_name>x500</target_name>
        <offset>0 -4 2.5 0 0.35 0</offset>
      </plugin>
    </gui>

    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 30 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.5 0.1 -0.9</direction>
    </light>

{lighting}
{slabs}
{walls}
{markers_xml}
  </world>
</sdf>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the three-floor disaster building SDF")
    ap.add_argument("--occlude", type=int, default=None,
                    help="marker ID to cover with an occluding slab (Phase 5 test)")
    ap.add_argument("--out", default=None, help="output path (default worlds/{WORLD_NAME}.sdf)")
    args = ap.parse_args()

    import yaml
    with open(MARKER_MAP, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    markers = {int(k): v for k, v in data["markers"].items()}

    out = Path(args.out) if args.out else OUT_DIR / f"{WORLD_NAME}.sdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_world(markers, args.occlude), encoding="utf-8")

    # sanity: the marker model dirs must exist for gazebo to resolve includes
    missing = [m for m in markers if not (ROOT / "src" / "drone_bringup" / "models"
                                          / f"marker_{m}" / "model.sdf").exists()]
    if missing:
        print(f"WARNING: {len(missing)} marker models missing "
              f"(e.g. marker_{missing[0]}) - run tools/generate_marker_models.py first")
    print(f"Wrote {out.relative_to(ROOT)} with {len(markers)} markers, "
          f"occlude={args.occlude}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())