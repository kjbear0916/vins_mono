#!/usr/bin/env python3
"""Scene generator for the 3-storey rescue building.

Single source of truth for layout. Emits:
  config/marker_map.yaml        marker id -> world pose (+kind/dict/size/floor)
  config/occlusion_zones.yaml   zones that require UWB anchor pre-deployment
  config/waypoint_routes.yaml   deterministic mission route incl. atrium climb
  worlds/building.sdf           3-storey building + markers + survivors + roof
  models/marker_<id>/...        marker model files (SDF + material script)
  models/anchor_model/...       UWB anchor visual model (spawned at runtime)
  models/survivor_model/...     survivor marker model (alias to marker magic)
  config/textures_generated.json flag whether real ArUco PNGs are present

Run:
  python3 make_scene.py build            # layout + placeholder materials
  python3 make_scene.py textures         # real ArUco PNGs (requires opencv)
  python3 make_scene.py show             # summary + encoding sanity checks
"""
import argparse
import json
import os
import sys

FLOORS = 3
FLOOR_H = 3.0
SLAB = 0.30
MAP_SIZE = 0.25
DICT = "7X7_1000"

# footprint: x in [0,20], y in [0,14]; corridor y in [0,3]; rooms y in [3.2,14]
BX = (0.0, 20.0)
BY = (0.0, 14.0)
CORR_Y = 3.0            # corridor room ceiling-wall line
ROOM_Y = 3.2
ATRIUM = ((8.67, 11.33), (ROOM_Y, 10.0))   # open vertical shaft (x-band, y-band)
FLOOR_GEOM = [          # slab pieces; P1/P2/P3/P4 around the atrium hole
    ((0.0, 20.0), (0.0, 3.0)),          # corridor
    ((0.0, 8.67), (3.2, 14.0)),
    ((11.33, 20.0), (3.2, 14.0)),
    ((8.67, 11.33), (10.0, 14.0)),
]
ROOMS = {1: ((0.0, 6.67), ROOM_Y, 14.0),
         2: ((6.67, 13.33), ROOM_Y, 14.0),
         3: ((13.33, 20.0), ROOM_Y, 14.0)}
ROOM_DOORS = {1: (4.0, 6.0), 2: (9.0, 11.0), 3: (14.0, 16.0)}
WALL_T = 0.20


def slab_top_z(floor):
    return (floor - 1) * FLOOR_H + SLAB


def flight_z(floor):
    return (floor - 1) * FLOOR_H + 1.8


def mk(id_, x, y, z, kind="waypoint", yaw=0.0):
    return {"id": id_, "x": x, "y": y, "z": z, "yaw": yaw,
            "kind": kind, "size": MAP_SIZE, "dict": DICT}


def build_marker_map():
    markers = {}
    for f in range(1, FLOORS + 1):
        z = slab_top_z(f) + 0.05
        corr = [(101 + i, x) for i, x in enumerate([2.0, 4.0, 6.0, 8.0, 12.0, 14.0, 16.0, 18.0])]
        for mid, x in corr:
            markers[mid + (f - 1) * 100] = mk(mid + (f - 1) * 100, x, 1.5, z)
        markers[f * 100 + 9] = mk(f * 100 + 9, 10.0, 2.2, z)          # atrium entrance
        markers[f * 100 + 11] = mk(f * 100 + 11, 2.0, 8.5, z)         # room 1
        markers[f * 100 + 12] = mk(f * 100 + 12, 5.0, 11.0, z)
        markers[f * 100 + 13] = mk(f * 100 + 13, 7.4, 7.0, z)         # room 2
        markers[f * 100 + 14] = mk(f * 100 + 14, 12.6, 7.0, z)
        markers[f * 100 + 15] = mk(f * 100 + 15, 16.0, 11.0, z)       # room 3
        markers[f * 100 + 16] = mk(f * 100 + 16, 18.0, 6.0, z)
    survivors = [
        mk(900, 3.0, 12.5, slab_top_z(1) + 0.05, kind="survivor"),
        mk(901, 10.0, 6.0, slab_top_z(2) + 0.05, kind="survivor"),
        mk(902, 17.0, 12.0, slab_top_z(3) + 0.05, kind="survivor"),
    ]
    for s in survivors:
        markers[s["id"]] = s
    return markers


def build_zones():
    zones = []
    for f in range(1, FLOORS + 1):
        zones.append({"id": f"atrium_{f}F", "type": "open_space",
                      "trigger_waypoint": f * 100 + 9, "risk_level": "high",
                      "radius_m": 5.0,
                      "note": "open vertical shaft, marker-free void"})
        zones.append({"id": f"atrium_door_corner_{f}F", "type": "corner",
                      "trigger_waypoint": f * 100 + 4, "risk_level": "medium",
                      "radius_m": 2.5})
    zones.append({"id": "demo_blind_2F_room2", "type": "manual_blind",
                  "trigger_waypoint": 206, "risk_level": "manual",
                  "radius_m": 3.0,
                  "note": "Phase 5 demo: temporarily shutter markers near 2F room 2"})
    return zones


def build_routes(markers):
    routes = {"floors": list(range(1, FLOORS + 1)), "atrium_entry_room_code": 9}
    for f in range(1, FLOORS + 1):
        base = f * 100
        nodes = [{"type": "marker", "id": base + 1}]
        for way in [2, 3, 4, 5, 6, 7, 8]:
            nodes.append({"type": "marker", "id": base + way})
        for room_wp in [11, 12, 13, 14, 15, 16]:
            nodes.append({"type": "marker", "id": base + room_wp})
        nodes.append({"type": "marker", "id": base + 9})       # atrium entrance
        if f < FLOORS:
            nodes.append({"type": "atrium_climb", "from_floor": f,
                          "hold_xy": [10.0, 5.0],
                          "exit_xy": [10.0, 2.2],
                          "to_floor": f + 1})
        routes[f"floor_{f}"] = nodes
    return routes


def escaped(x):
    return f"{x:.3f}".rstrip("0").rstrip(".")


def px(x):
    return escaped((x[0] + x[1]) / 2.0)


def wdt(x):
    return escaped(x[1] - x[0])


def sdf_box(link, cx, cy, cz, sx, sy, sz, r=0.15, g=0.15, b=0.15, static=True):
    return f"""      <link name='{link}'>
        <pose>{cx} {cy} {cz} 0 0 0</pose>
        <visual name='v'>
          <geometry><box><size>{sx} {sy} {sz}</size></box></geometry>
          <material><ambient>{r} {g} {b} 1</ambient><diffuse>{r} {g} {b} 1</diffuse></material>
        </visual>
        <collision name='c'>
          <geometry><box><size>{sx} {sy} {sz}</size></box></geometry>
        </collision>
      </link>"""


def build_geometry_links():
    links, i = [], 0
    for xb, yb in FLOOR_GEOM:
        for f in range(1, FLOORS + 1):
            z = (f - 1) * FLOOR_H
            links.append(sdf_box(f"slab_f{f}_{i}", px(xb), px(yb), z + SLAB / 2,
                                 wdt(xb), wdt(yb), SLAB, 0.75, 0.75, 0.75))
            i += 1
    for f in range(1, FLOORS + 1):
        z0 = (f - 1) * FLOOR_H + SLAB
        h = FLOOR_H - SLAB
        links.append(sdf_box(f"ceil_f{f}", 10.0, 7.0, z0 + h, 20.4, 14.4, WALL_T,
                             0.8, 0.8, 0.8))
    for (xb, yb, top) in ROOMS.values():
        pass
    return links


def sdf_wall_piece(link, x0, x1, y, z0, z1, t=WALL_T):
    return sdf_box(link, px((x0, x1)), y, (z0 + z1) / 2, wdt((x0, x1)), t, z1 - z0, 0.55, 0.55, 0.6)


def sdf_wall_vertical(link, x, y0, y1, z0, z1, t=WALL_T):
    return sdf_box(link, x, px((y0, y1)), (z0 + z1) / 2, t, wdt((y0, y1)), z1 - z0, 0.55, 0.55, 0.6)


def build_wall_links():
    links = []
    for f in range(1, FLOORS + 1):
        z0 = (f - 1) * FLOOR_H + SLAB
        z1 = z0 + (FLOOR_H - SLAB) * 0.9
        # exterior
        links.append(sdf_wall_piece(f"ext_s_f{f}", 0.0, 20.0, 0.0, z0, z1))
        links.append(sdf_wall_piece(f"ext_n_f{f}", 0.0, 20.0, 14.0, z0, z1))
        links.append(sdf_wall_vertical(f"ext_w_f{f}", 0.0, 0.0, 14.0, z0, z1))
        links.append(sdf_wall_vertical(f"ext_e_f{f}", 20.0, 0.0, 14.0, z0, z1))
        # corridor <-> rooms wall (y=3) with door gaps
        gaps = [(4.0, 6.0), (8.67, 11.33), (14.0, 16.0)]
        seg = [(0.0, 4.0), (6.0, 8.67), (11.33, 14.0), (16.0, 20.0)]
        for k, (a, b) in enumerate(seg):
            links.append(sdf_wall_piece(f"corrwall_f{f}_{k}", a, b, CORR_Y, z0, z1))
        # room dividers x=6.67 / x=13.33 (door gap 8..10)
        links.append(sdf_wall_vertical(f"roomdiv_a_f{f}", 6.67, 3.2, 8.0, z0, z1))
        links.append(sdf_wall_vertical(f"roomdiv_a2_f{f}", 6.67, 10.0, 14.0, z0, z1))
        links.append(sdf_wall_vertical(f"roomdiv_b_f{f}", 13.33, 3.2, 8.0, z0, z1))
        links.append(sdf_wall_vertical(f"roomdiv_b2_f{f}", 13.33, 10.0, 14.0, z0, z1))
        # atrium enclosure
        links.append(sdf_wall_vertical(f"atr_w_f{f}", 8.67, 3.2, 10.0, z0, z1))
        links.append(sdf_wall_vertical(f"atr_e_f{f}", 11.33, 3.2, 10.0, z0, z1))
        links.append(sdf_wall_piece(f"atr_back_f{f}", 8.67, 11.33, 10.0, z0, z1))
        # room2 access openings in atrium walls
        links.append(sdf_wall_vertical(f"atr_w_door_f{f}", 8.67, 3.2, 6.0, z0, z1))
        links.append(sdf_wall_vertical(f"atr_e_door_f{f}", 11.33, 3.2, 6.0, z0, z1))
    return links


def material_block(marker_id, real_textures):
    if real_textures:
        return (f"      <material><script><uri>model://marker_{marker_id}/materials/scripts/"
                f"aruco_{marker_id}.material</uri><name>aruco/{marker_id}</name></script></material>")
    import hashlib
    h = hashlib.md5(str(marker_id).encode()).digest()
    r, g, b = h[0] / 255.0, h[1] / 255.0, h[2] / 255.0
    return f"      <material><ambient>{r:.3f} {g:.3f} {b:.3f} 1</ambient><diffuse>{r:.3f} {g:.3f} {b:.3f} 1</diffuse></material>"


def marker_model_sdf(mid, x, y, z, real_textures):
    return f"""<?xml version='1.0'?>
<sdf version='1.8'>
  <model name='marker_{mid}'>
    <static>true</static>
    <self_collide>false</self_collide>
    <link name='plate'>
      <pose>{x} {y} {z} 0 0 0</pose>
      <visual name='v'>
        <geometry><box><size>{MAP_SIZE} 0.003 {MAP_SIZE}</size></box></geometry>
{material_block(mid, real_textures)}
      </visual>
    </link>
  </model>
</sdf>
"""


def anchor_model_sdf():
    return """<?xml version='1.0'?>
<sdf version='1.8'>
  <model name='{name}'>
    <static>true</static>
    <link name='body'>
      <pose>0 0 0 0 0 0</pose>
      <visual name='v'>
        <geometry><box><size>0.12 0.12 0.12</size></box></geometry>
        <material><ambient>0.0 1.0 0.0 1</ambient><diffuse>0.0 1.0 0.0 1</diffuse><emissive>0.0 0.9 0.0 1</emissive></material>
      </visual>
    </link>
  </model>
</sdf>
"""


def marker_model_config(mid):
    return f"""<?xml version='1.0'?>
<model>
  <name>marker_{mid}</name>
  <version>1.0</version>
  <sdf version='1.8'>model.sdf</sdf>
</model>
"""


def write_material_script(mid, real_textures, out_dir):
    if not real_textures:
        return
    scripts_dir = os.path.join(out_dir, f"marker_{mid}/materials/scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    with open(os.path.join(scripts_dir, f"aruco_{mid}.material"), "w") as fh:
        fh.write(f"""aruco/{mid}
{{
  technique
  {{
    pass
    {{
      lighting off
      texture_unit
      {{
        texture aruco_{mid}.png
      }}
    }}
  }}
}}
""")


def write_real_textures(markers, out_dir):
    try:
        import cv2
    except ImportError:
        print("cv2 not available; placeholders stay in effect", file=sys.stderr)
        return False
    aruco = cv2.aruco
    dic = aruco.getPredefinedDictionary(aruco.DICT_7X7_1000)
    scripts = "materials/scripts"
    for mid in sorted(markers.keys()):
        img = aruco.drawMarker(dic, mid, int(MAP_SIZE * 400), 1)
        scripts_dir = os.path.join(out_dir, f"marker_{mid}", scripts)
        os.makedirs(scripts_dir, exist_ok=True)
        cv2.imwrite(os.path.join(scripts_dir, f"aruco_{mid}.png"), img)
    return True


def build_sdf(markers, real_textures):
    links = build_geometry_links() + build_wall_links()
    geom = "\n".join(links)
    marker_inc = []
    for m in markers.values():
        marker_inc.append(
            f"  <include><uri>model://marker_{m['id']}</uri><pose>{m['x']} {m['y']} {m['z']} 0 0 {m['yaw']}</pose></include>")
    top = f"""<?xml version='1.0'?>
<sdf version='1.8'>
  <world name='building'>
    <physics name='default' type='ode'><gravity>0 0 -9.81</gravity></physics>
    <scene><ambient>0.5 0.5 0.5</ambient><background>0.25 0.25 0.3</background></scene>
    <include><uri>model://ground_plane</uri></include>
    <include><uri>model://sun</uri></include>
    <model name='building_geometry'>
      <static>true</static>
      <link name='anchor'>
        <pose>0 0 0 0 0 0</pose>
        <inertial><mass>0</mass></inertial>
        <visual name='v'>
          <geometry><box><size>21 15 0.5</size></box></geometry>
          <material><ambient>0.3 0.3 0.3 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material>
        </visual>
      </link>
{geom}
    </model>
{chr(10).join(marker_inc)}
  </world>
</sdf>
"""
    return top


def _yaml_scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return f"{round(v, 3):.3f}".rstrip("0").rstrip(".")
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def dict_dump(path, data):
    lines = []
    for key, node in data.items():
        if isinstance(node, dict):
            lines.append(f"{key}:")
            for k2, v2 in node.items():
                if isinstance(v2, dict):
                    lines.append(f"  {k2}:")
                    for k3, v3 in v2.items():
                        lines.append(f"    {k3}: {_yaml_scalar(v3)}")
                else:
                    lines.append(f"  {k2}: {_yaml_scalar(v2)}")
        elif isinstance(node, list):
            lines.append(f"{key}:")
            for item in node:
                if isinstance(item, dict):
                    lines.append("  -")
                    for k2, v2 in item.items():
                        lines.append(f"    {k2}: {_yaml_scalar(v2)}")
                else:
                    lines.append(f"  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {_yaml_scalar(node)}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "textures", "show"])
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    pkg = os.path.abspath(os.path.join(here, ".."))
    cfg, wld, mdl = (os.path.join(pkg, d) for d in ("config", "worlds", "models"))
    for d in (cfg, wld, mdl):
        os.makedirs(d, exist_ok=True)

    markers = build_marker_map()
    zones = build_zones()
    routes = build_routes(markers)

    if args.cmd == "show":
        kinds = {}
        for m in markers.values():
            kinds[m["kind"]] = kinds.get(m["kind"], 0) + 1
        ids = sorted(markers)
        assert len(ids) == len(set(ids)), "duplicate marker ids"
        assert all(900 <= i <= 999 or 100 <= i <= 399 for i in ids), "id outside scheme"
        print(f"markers: {len(ids)}  kinds={kinds}")
        print("zones:", len(zones), " floors:", FLOORS)
        for f in range(1, FLOORS + 1):
            print(f"  floor {f}: corridor 1-8, atrium-entry {f}09, rooms 11-16")
        return

    real = os.path.exists(os.path.join(cfg, "textures_generated.json"))
    if args.cmd == "textures":
        real = write_real_textures(markers, cfg)
        with open(os.path.join(cfg, "textures_generated.json"), "w") as fh:
            json.dump({"generated": real, "dict": DICT}, fh)
        print("textures_generated.json written; regenerating sdf")
        if not real:
            return

    for m in markers.values():
        mdir = os.path.join(mdl, f"marker_{m['id']}")
        os.makedirs(mdir, exist_ok=True)
        with open(os.path.join(mdir, "model.sdf"), "w") as fh:
            fh.write(marker_model_sdf(m["id"], 0, 0, 0, real))
        with open(os.path.join(mdir, "model.config"), "w") as fh:
            fh.write(marker_model_config(m["id"]))
        write_material_script(m["id"], real, mdl)

    amdir = os.path.join(mdl, "anchor_model")
    os.makedirs(amdir, exist_ok=True)
    with open(os.path.join(amdir, "model.sdf"), "w") as fh:
        fh.write(anchor_model_sdf())
    with open(os.path.join(amdir, "model.config"), "w") as fh:
        fh.write("""<?xml version='1.0'?>
<model>
  <name>anchor_model</name>
  <version>1.0</version>
  <sdf version='1.8'>model.sdf</sdf>
</model>
""")

    dict_dump(os.path.join(cfg, "marker_map.yaml"),
              {"dictionary": DICT, "marker_size_m": MAP_SIZE, "markers": markers})
    dict_dump(os.path.join(cfg, "occlusion_zones.yaml"), {"zones": zones})
    dict_dump(os.path.join(cfg, "waypoint_routes.yaml"), routes)
    with open(os.path.join(wld, "building.sdf"), "w") as fh:
        fh.write(build_sdf(markers, real))
    print(f"wrote {os.path.join(wld, 'building.sdf')}")
    if not real:
        print("NOTE: placeholder materials active; run `make_scene.py textures` in the ROS container")


if __name__ == "__main__":
    main()