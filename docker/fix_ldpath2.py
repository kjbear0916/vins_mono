import pathlib
f = pathlib.Path('/root/sim_launch.sh')
t = f.read_text()
old = 'LD_LIBRARY_PATH=/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:$LD_LIBRARY_PATH'
new = 'LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/root/catkin_ws/devel/lib:/opt/ros/noetic/lib:/root/PX4-Autopilot/build/px4_sitl_default/build_gazebo-classic:$LD_LIBRARY_PATH'
t = t.replace(old, new, 1)
f.write_text(t)
print('OK')
