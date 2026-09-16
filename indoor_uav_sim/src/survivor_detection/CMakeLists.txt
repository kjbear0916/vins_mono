cmake_minimum_required(VERSION 3.8)
project(survivor_detection)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  survivor_detection/survivor_detector_node.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
