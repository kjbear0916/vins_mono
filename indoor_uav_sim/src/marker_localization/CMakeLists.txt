cmake_minimum_required(VERSION 3.8)
project(marker_localization)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  marker_localization/marker_detector_node.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
