import io

p = r"/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/src/gazebo_mavlink_interface.cpp"
with io.open(p, encoding="utf-8") as f:
    s = f.read()

old = '  gzdbg << "[MAVLINKDBG] ImuCallback\\n";\n{\n  std::unique_lock<std::mutex> lock(imu_received_mutex_);'
new = '  gzdbg << "[MAVLINKDBG] ImuCallback\\n";\n  std::unique_lock<std::mutex> lock(imu_received_mutex_);'
assert s.count(old) == 1, "count=%d" % s.count(old)
s = s.replace(old, new)

with io.open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(s)
print("fixed imu callback brace OK")