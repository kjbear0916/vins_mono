# UWB anchor point deployed in the environment
std_msgs/Header header
int32 anchor_id
geometry_msgs/Pose pose
bool is_deployed     # true = physically placed, false = planned
float64 range_std    # noise std for ranging simulation
