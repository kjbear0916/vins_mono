"""Phase 5: UWB anchor deployment and visual-occlusion fallback."""
import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_share = get_package_share_directory("drone_bringup")
    marker_map = os.path.join(pkg_share, "config", "marker_map.yaml")
    uwb_params = os.path.join(pkg_share, "config", "uwb_params.yaml")

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
            package="uwb_localization",
            executable="anchor_manager_node.py",
            name="anchor_manager",
            parameters=[{
                "deployed_anchors_file": os.path.join(pkg_share, "config", "deployed_anchors.yaml"),
                "spawn_gz_models": True,
            }],
            output="screen",
        ),
        Node(
            package="uwb_localization",
            executable="uwb_ranging_sim_node.py",
            name="uwb_ranging_sim",
            parameters=[{
                "effective_range": 15.0,
                "noise_std": 0.2,
            }],
            output="screen",
        ),
        Node(
            package="uwb_localization",
            executable="uwb_trilateration_node.py",
            name="uwb_trilateration",
            parameters=[{
                "min_anchors": 4,
                "max_iterations": 100,
            }],
            output="screen",
        ),
        Node(
            package="pose_fusion",
            executable="pose_fusion_node.py",
            name="pose_fusion",
            parameters=[{
                "occlusion_zones_file": os.path.join(pkg_share, "config", "occlusion_zones.yaml"),
                "aruco_lost_frames": 5,
                "aruco_recover_frames": 3,
                "aruco_confidence_min": 0.3,
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
    ])
