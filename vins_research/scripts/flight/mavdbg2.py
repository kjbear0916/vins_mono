import io

p = r"/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/src/gazebo_mavlink_interface.cpp"
with io.open(p, encoding="utf-8") as f:
    s = f.read()

old_imu = "void GazeboMavlinkInterface::ImuCallback(ImuPtr& imu_message)"
new_imu = "void GazeboMavlinkInterface::ImuCallback(ImuPtr& imu_message)\n{\n  gzdbg << \"[MAVLINKDBG] ImuCallback\\n\";"
assert s.count(old_imu) == 1, "imu old count %d" % s.count(old_imu)
s = s.replace(old_imu, new_imu)

with io.open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(s)
print("patched imu cb OK")