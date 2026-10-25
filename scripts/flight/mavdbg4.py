import io

p = r"/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/src/gazebo_mavlink_interface.cpp"
with io.open(p, encoding="utf-8") as f:
    s = f.read()

pairs = [
    ("void GazeboMavlinkInterface::MagnetometerCallback(MagnetometerPtr& mag_msg) {\n  SensorData::Magnetometer mag_data;",
     'void GazeboMavlinkInterface::MagnetometerCallback(MagnetometerPtr& mag_msg) {\n  gzdbg << "[MAVLINKDBG] MagnetometerCallback b=" << mag_msg->magnetic_field().x() << "," << mag_msg->magnetic_field().y() << "," << mag_msg->magnetic_field().z() << "\\n";\n  SensorData::Magnetometer mag_data;'),
    ("void GazeboMavlinkInterface::BarometerCallback(BarometerPtr& baro_msg) {\n  SensorData::Barometer baro_data;",
     'void GazeboMavlinkInterface::BarometerCallback(BarometerPtr& baro_msg) {\n  gzdbg << "[MAVLINKDBG] BarometerCallback p=" << baro_msg->absolute_pressure() << " alt=" << baro_msg->pressure_altitude() << "\\n";\n  SensorData::Barometer baro_data;'),
]
for old, new in pairs:
    n = s.count(old)
    assert n == 1, "count=%d for %r" % (n, old[:60])
    s = s.replace(old, new)

with io.open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(s)
print("mag+baro callbacks patched OK")