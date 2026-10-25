#!/bin/bash
echo '=== Ceres ==='
ls /usr/local/lib/libceres* 2>/dev/null | head -2
echo '=== PX4 ==='
[ -f /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 ] && echo 'px4 binary OK' || echo 'px4 MISSING'
echo '=== catkin devel ==='
[ -f /root/catkin_ws/devel/lib/vins_estimator/vins_estimator ] && echo 'vins_estimator OK' || echo 'vins_estimator MISSING'
[ -f /root/catkin_ws/devel/lib/mavros/mavros_node ] && echo 'mavros_node OK' || echo 'mavros_node MISSING'
echo '=== Python ==='
python3 -c 'import evo; print("evo", evo.__version__)'
python3 -c 'import numpy; print("numpy", numpy.__version__)'
python3 -c 'import pandas; print("pandas", pandas.__version__)'
echo '=== source packages ==='
ls /root/catkin_ws/src/
