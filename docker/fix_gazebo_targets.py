import pathlib
f = pathlib.Path('/root/PX4-Autopilot/src/modules/simulation/simulator_mavlink/sitl_targets_gazebo-classic.cmake')
t = f.read_text()
old = """		CMAKE_ARGS
			-DCMAKE_INSTALL_PREFIX=${CMAKE_INSTALL_PREFIX}
			-DSEND_ODOMETRY_DATA=ON
			-DGENERATE_ROS_MODELS=ON"""
new = """		CMAKE_ARGS
			-DCMAKE_INSTALL_PREFIX=${CMAKE_INSTALL_PREFIX}
			-DSEND_ODOMETRY_DATA=ON
			-DGENERATE_ROS_MODELS=ON
			-DBUILD_GSTREAMER_PLUGIN=OFF
			-D_MAVLINK_INCLUDE_DIR=${PX4_BINARY_DIR}"""
assert old in t, 'pattern not found'
t = t.replace(old, new, 1)
f.write_text(t)
print('OK')
