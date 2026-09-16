"""Phase 6: Survivor detection and reporting."""
import os
from launch import LaunchDescription
from launch_ros.actions import Node
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
            }],
            output="screen",
        ),
        Node(
            package="survivor_detection",
            executable="survivor_detector_node.py",
            name="survivor_detector",
            parameters=[{
                "camera_topic": "/drone/camera/front/image_raw",
                "marker_map_file": marker_map,
                "marker_size_m": 0.5,
                "min_confidence": 0.4,
            }],
            output="screen",
        ),
        Node(
            package="obstacle_avoidance",
            executable="obstacle_avoider_node.py",
            name="obstacle_avoider",
            parameters=[{
                "safety_distance": 1.5,
                "slow_distance": 2.5,
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
            }],
            output="screen",
        ),
        Node(
            package="mission_control",
            executable="mission_planner_node.py",
            name="mission_planner",
            parameters=[{
                "mission_file": os.path.join(pkg_share, "config", "mission_waypoints.yaml"),
            }],
            output="screen",
        ),
    ])
