import pathlib
f = pathlib.Path('/root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_run.sh')
t = f.read_text()
old = '\tgzserver $verbose $world_path $ros_args &'
new = '\tif [ -z "$DISPLAY" ] && [ -x "$(command -v xvfb-run)" ]; then\n\t\tgzserver_cmd="xvfb-run -a -s \\"-screen 0 1920x1080x24\\" gzserver $verbose $world_path $ros_args"\n\telse\n\t\tgzserver_cmd="gzserver $verbose $world_path $ros_args"\n\tfi\n\teval $gzserver_cmd &'
if old not in t:
    # fallback: maybe tabs vs spaces
    old = 'gzserver $verbose $world_path $ros_args &'
    assert old in t, 'pattern not found'
    t = t.replace(old, new.replace('\t', '  '), 1)
else:
    t = t.replace(old, new, 1)
f.write_text(t)
print('OK')
