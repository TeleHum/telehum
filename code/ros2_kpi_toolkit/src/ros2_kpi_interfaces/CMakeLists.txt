cmake_minimum_required(VERSION 3.10)
project(ros2_kpi_interfaces)

# ROS 2 Humble still pulls legacy Python find modules through rosidl on newer CMake.
if(POLICY CMP0148)
  cmake_policy(SET CMP0148 OLD)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/KpiProbe.msg"
  "msg/KpiSample.msg"
  "msg/KpiWindowMetrics.msg"
  "msg/KpiWindowStats.msg"
  DEPENDENCIES builtin_interfaces std_msgs
)

ament_export_dependencies(rosidl_default_runtime)

ament_package()
