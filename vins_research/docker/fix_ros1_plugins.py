import pathlib
f = pathlib.Path('/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_run.sh')
t = f.read_text()
old = '\tros_args=""'
new = '\tros_args="-s libgazebo_ros_api_plugin.so -s libgazebo_ros_paths_plugin.so"'
count = 0
# only first occurrence (the else branch)
idx = t.find(old)
assert idx != -1, 'pattern not found'
t = t[:idx] + new + t[idx+len(old):]
f.write_text(t)
print('OK')
