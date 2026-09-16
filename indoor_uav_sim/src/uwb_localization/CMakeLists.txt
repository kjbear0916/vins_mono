cmake_minimum_required(VERSION 3.8)
project(uwb_localization)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  uwb_localization/anchor_manager_node.py
  uwb_localization/uwb_ranging_sim_node.py
  uwb_localization/uwb_trilateration_node.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
