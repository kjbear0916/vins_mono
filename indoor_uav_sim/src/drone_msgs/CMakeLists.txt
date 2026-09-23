cmake_minimum_required(VERSION 3.15)
project(drone_msgs)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(msg_files
  "msg/MarkerPose.msg"
  "msg/UwbAnchor.msg"
  "msg/UwbRange.msg"
  "msg/SurvivorReport.msg"
  "msg/MissionStatus.msg"
  "msg/FusedPose.msg"
  "msg/AnchorDeployment.msg"
  "msg/LoomingThreat.msg"
)

set(srv_files
)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${msg_files}
  ${srv_files}
  DEPENDENCIES std_msgs geometry_msgs builtin_interfaces
)

ament_package()