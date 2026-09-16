cmake_minimum_required(VERSION 3.8)
project(marker_navigation)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  marker_navigation/waypoint_navigator_node.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
