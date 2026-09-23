cmake_minimum_required(VERSION 3.8)
project(mission_control)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  mission_control/mission_planner_node.py
  DESTINATION lib/${PROJECT_NAME}
)



ament_package()
