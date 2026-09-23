import io

p = r"/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/src/gazebo_barometer_plugin.cpp"
with io.open(p, encoding="utf-8") as f:
    s = f.read()

old = "  const double dt = (current_time - last_pub_time_).Double();\n"
new = old + '  gzdbg << "[BARODBG] OnUpdate dt=" << dt << " pub_rate=" << pub_rate_ << "\\n";\n'

assert s.count(old) == 1, "OLD count = %d" % s.count(old)
with io.open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(s.replace(old, new))
print("patched OK")