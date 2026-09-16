"""Phase 1: Single corridor marker navigation."""
import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_share = get_package_share_directory("drone_bringup")

    marker_map = os.path.join(pkg_share, "config", "marker_map.yaml")

    return LaunchDescription([
        Node(
            package="marker_localization",
            executable="marker_detector_node.py",
            name="marker_detector",
            parameters=[{
                "camera_topic": "/drone/camera/nadir/image_raw",
                "marker_map_file": marker_map,
                "marker_size_m": 0.5,
            }],
            output="screen",
        ),
        Node(
            package="marker_navigation",
            executable="waypoint_navigator_node.py",
            name="waypoint_navigator",
            parameters=[{
                "marker_map_file": marker_map,
                "mission_file": os.path.join(pkg_share, "config", "mission_waypoints.yaml"),
                "occlusion_zones_file": os.path.join(pkg_share, "config", "occlusion_zones.yaml"),
                "position_kp": 0.8,
                "yaw_kp": 1.0,
                "position_tolerance": 0.3,
            }],
            output="screen",
        ),
    ])
