# Mission status update
std_msgs/Header header
string phase               # "idle" / "exploring" / "changing_floor" / "returning" / "complete"
int32 current_floor
int32 current_waypoint
int32 total_waypoints
string position_source     # "aruco" / "uwb"
int32 anchors_deployed
string[] survivors_found
