cmake_minimum_required(VERSION 3.8)
project(obstacle_avoidance)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  obstacle_avoidance/obstacle_avoider_node.py
  obstacle_avoidance/looming_detector_node.py
  obstacle_avoidance/fly_vision.py
  DESTINATION lib/${PROJECT_NAME}
)



ament_package()
