# Survivor detection report
std_msgs/Header header
int32 survivor_id
geometry_msgs/Pose pose       # world coordinates from fused_pose at detection time
float64 confidence
string marker_type            # "aruco_900_999" or "color"
