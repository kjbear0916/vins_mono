cmake_minimum_required(VERSION 3.8)
project(pose_fusion)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  pose_fusion/pose_fusion_node.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
