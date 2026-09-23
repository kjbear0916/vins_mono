import pathlib
f = pathlib.Path('/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_run.sh')
t = f.read_text()
old = 'export PX4_SIM_MODEL=gazebo-classic_${model}'
new = 'if [ -z "$PX4_SIM_MODEL" ]; then export PX4_SIM_MODEL=gazebo-classic_${model}; fi'
assert old in t, 'pattern not found'
t = t.replace(old, new, 1)
f.write_text(t)
print('OK')
