#!/bin/bash
# setup_sim_assets.sh — (re)install the simulation runtime assets that the stock
# PX4 build does NOT produce. Historically these were applied by hand inside the
# container and were silently lost on every container recreate; this script is
# the single source of truth. It is run both at image-build time (Dockerfile) and
# manually after a container recreate:
#
#   bash /root/catkin_ws/src/vins_research/docker/setup_sim_assets.sh
#
# It is idempotent: every step checks its own precondition first, so a second run
# (or a run on an already-provisioned container) is a harmless no-op.
#
# The six assets baked here:
#   1. apt deps: libgstreamer1.0-dev / libgstreamer-plugins-base1.0-dev / xvfb /
#      geographiclib-tools
#   2. rendered jinja models (e.g. models/iris/iris.sdf) — PX4 ships only .jinja
#   3. the gazebo-classic plugins (build_gazebo-classic/*.so) — not built by
#      `make px4_sitl_default`
#   4. three sitl_run.sh patches (PX4_SIM_MODEL guard, ROS1 process plugins, xvfb)
#   5. the custom world (vins_demo.world) + model (vins_props)
#   6. the GeographicLib geoid dataset (egm96-5.pgm)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSETS="${ASSETS_DIR:-$HERE/assets}"
PX4=/root/PX4-Autopilot
PKG="$PX4/Tools/simulation/gazebo-classic/sitl_gazebo-classic"
BD="$PX4/build/px4_sitl_default/build_gazebo-classic"

echo "=== [1/6] apt deps (gstreamer dev, xvfb, geoid tools) ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
  xvfb geographiclib-tools

echo "=== [2/6] render missing jinja models ==="
for j in "$PKG"/models/*/*.sdf.jinja; do
  [ -e "$j" ] || continue
  sdf="${j%.jinja}"
  if [ ! -f "$sdf" ]; then
    echo "  render $sdf"
    python3 "$PKG/scripts/jinja_gen.py" "$j" "$PKG"
  fi
done

echo "=== [3/6] build gazebo-classic plugins ==="
if ls "$BD"/*.so >/dev/null 2>&1; then
  echo "  plugins present ($(ls "$BD"/*.so | wc -l) .so) — skip"
else
  mkdir -p "$BD"
  cd "$BD"
  cmake -DCMAKE_INSTALL_PREFIX=/usr/local -DSEND_ODOMETRY_DATA=ON \
        -DGENERATE_ROS_MODELS=ON -GNinja "$PKG"
  cmake --build . -- -j"$(nproc)"
fi

echo "=== [4/6] apply sitl_run.sh patches (idempotent) ==="
python3 "$HERE/fix_sitl_run.py"
python3 "$HERE/fix_ros1_plugins.py"
python3 "$HERE/fix_xvfb.py"

echo "=== [5/6] install custom world + model ==="
mkdir -p "$PKG/models/vins_props"
cp -f "$ASSETS/vins_props/vins_props.sdf" "$PKG/models/vins_props/vins_props.sdf"
cp -f "$ASSETS/vins_props/model.config"   "$PKG/models/vins_props/model.config"
cp -f "$ASSETS/vins_demo.world"           "$PKG/worlds/vins_demo.world"
# iris_fpv_cam camera-pitch override: the jinja render in [2/6] regenerates
# iris_fpv_cam.sdf with the stock level camera, but the RIC in
# config/sim_config.yaml assumes the ~0.6 rad downward pitch used by the
# original 54-run; without it VINS init collapses (scale ~1.37, ATE ~5 m).
# The preserved original (data/_iris_fpv_cam.sdf) carries pose roll/pitch/yaw
# "0 0.6 0"; restore it here so the bake keeps it.
cp -f "$ASSETS/iris_fpv_cam/iris_fpv_cam.sdf" "$PKG/models/iris_fpv_cam/iris_fpv_cam.sdf"
# light-axis worlds: identical scene to vins_demo, differ ONLY in <scene>/<light>.
# trial_one.sh selects these by LIGHT so the three 'light' arms really run
# different scenes (before the fix the light axis was silently inert).
for lw in light_high light_medium light_low; do
  cp -f "$ASSETS/$lw.world" "$PKG/worlds/$lw.world"
done

echo "=== [6/6] geoid dataset ==="
if [ ! -f /usr/share/GeographicLib/geoids/egm96-5.pgm ]; then
  for spec in egm96-5 low default; do
    geographiclib-get-geoids "$spec" || true
    [ -f /usr/share/GeographicLib/geoids/egm96-5.pgm ] && break
  done
fi
if [ -f /usr/share/GeographicLib/geoids/egm96-5.pgm ]; then
  echo "  egm96-5.pgm OK"
else
  echo "  WARN egm96-5.pgm missing"
fi

echo "SETUP_SIM_ASSETS_DONE"
