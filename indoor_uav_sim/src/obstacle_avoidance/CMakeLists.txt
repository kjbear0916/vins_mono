cmake_minimum_required(VERSION 3.8)
project(obstacle_avoidance)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  obstacle_avoidance/obstacle_avoider_node.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
