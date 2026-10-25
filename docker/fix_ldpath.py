import pathlib
f = pathlib.Path('/root/sim_launch.sh')
t = f.read_text()
# add gazebo-11 plugins to LD_LIBRARY_PATH and GAZEBO_PLUGIN_PATH
t = t.replace(
    'LD_LIBRARY_PATH=/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:$LD_LIBRARY_PATH',
    'LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:$LD_LIBRARY_PATH'
)
# also add the path to GAZEBO_PLUGIN_PATH
t = t.replace(
    'GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/opt/ros/noetic/lib',
    'GAZEBO_PLUGIN_PATH=/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/opt/ros/noetic/lib'
)
f.write_text(t)
print('OK')
