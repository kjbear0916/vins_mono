import io

p = r"/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/src/gazebo_mavlink_interface.cpp"
with io.open(p, encoding="utf-8") as f:
    s = f.read()

# mag callback print
old_mag = """void GazeboMavlinkInterface::MagnetometerCallback(MagnetometerPtr& mag_msg) {
  SensorData::Magnetometer mag_data;"""
new_mag = """void GazeboMavlinkInterface::MagnetometerCallback(MagnetometerPtr& mag_msg) {
  gzdbg << "[MAVLINKDBG] MagnetometerCallback b=" << mag_msg->magnetic_field().x() << "," << mag_msg->magnetic_field().y() << "," << mag_msg->magnetic_field().z() << "\\n";
  SensorData::Magnetometer mag_data;"""
assert s.count(old_mag) == 1, "mag old count %d" % s.count(old_mag)
s = s.replace(old_mag, new_mag)

# baro callback print
old_baro = """void GazeboMavlinkInterface::BarometerCallback(BarometerPtr& baro_msg) {
  SensorData::Barometer baro_data;"""
new_baro = """void GazeboMavlinkInterface::BarometerCallback(BarometerPtr& baro_msg) {
  gzdbg << "[MAVLINKDBG] BarometerCallback p=" << baro_msg->absolute_pressure() << " alt=" << baro_msg->pressure_altitude() << "\\n";
  SensorData::Barometer baro_data;"""
assert s.count(old_baro) == 1, "baro old count %d" % s.count(old_baro)
s = s.replace(old_baro, new_baro)

# imu callback print
old_imu = """void GazeboMavlinkInterface::ImuCallback(ImuPtr& imu_msg) {"""
new_imu = """void GazeboMavlinkInterface::ImuCallback(ImuPtr& imu_msg) {
  gzdbg << "[MAVLINKDBG] ImuCallback\\n";"""
assert s.count(old_imu) == 1, "imu old count %d" % s.count(old_imu)
s = s.replace(old_imu, new_imu)

with io.open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(s)
print("patched mavlink_interface OK")