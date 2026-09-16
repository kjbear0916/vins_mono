cmake_minimum_required(VERSION 3.8)
project(drone_control)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  drone_control/drone_control_node.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()