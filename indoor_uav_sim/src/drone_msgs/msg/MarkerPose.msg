# Detected ArUco marker pose in world coordinates
std_msgs/Header header
int32 marker_id
geometry_msgs/Pose pose
float64 confidence  # 0.0-1.0, based on detection quality
float64 distance    # distance from camera to marker in meters
