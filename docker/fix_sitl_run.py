import pathlib
f = pathlib.Path('/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_run.sh')
t = f.read_text()
old = 'export PX4_SIM_MODEL=gazebo-classic_${model}'
new = 'if [ -z "$PX4_SIM_MODEL" ]; then export PX4_SIM_MODEL=gazebo-classic_${model}; fi'
if new in t:
    print('already patched (idempotent, no-op)')
else:
    assert old in t, 'pattern not found'
    f.write_text(t.replace(old, new, 1))
    print('OK patched')
