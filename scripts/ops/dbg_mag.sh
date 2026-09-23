#!/bin/bash
cd /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic
cp src/gazebo_magnetometer_plugin.cpp /tmp/gazebo_magnetometer_plugin.cpp.bak

# insert debug print at start of OnUpdate
python3 - <<'PYEOF'
p = 'src/gazebo_magnetometer_plugin.cpp'
s = open(p).read()
needle = """double dt = (current_time - last_pub_time_).Double();

  if (dt > 1.0 / pub_rate_) {"""
dbg = """double dt = (current_time - last_pub_time_).Double();
  gzdbg << "[MAGDBG] OnUpdate dt=" << dt << " pub_rate=" << pub_rate_ << "\\n";

  if (dt > 1.0 / pub_rate_) {"""
assert needle in s, "needle not found"
s = s.replace(needle, dbg, 1)
open(p, 'w').write(s)
print("patched")
PYEOF

cd /root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic
ninja libgazebo_magnetometer_plugin.so 2>&1 | tail -3
echo "=== rebuild done ==="