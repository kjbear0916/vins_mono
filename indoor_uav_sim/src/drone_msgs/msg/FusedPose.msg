# Pose with validity flag for fusion
std_msgs/Header header
geometry_msgs/PoseWithCovariance pose
float64 confidence
string source              # "aruco" / "uwb" / "dead_reckoning"
bool is_valid