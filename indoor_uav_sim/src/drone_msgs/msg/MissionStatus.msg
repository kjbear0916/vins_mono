# Mission status update
std_msgs/Header header
string mission_phase       # "idle" / "exploring" / "changing_floor" / "returning" / "complete"
int32 current_floor
int32 current_waypoint_id
int32 num_anchors_deployed
int32 num_survivors_found
string localization_source # "aruco" / "uwb"
float64 elapsed_time