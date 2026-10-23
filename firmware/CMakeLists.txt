# The watch firmware. Its build files start from examples/esp-idf/02_lvgl_demo_v9
# in Waveshare's repo at commit 30f3b23, with the demo apps left out. The shared
# C library in core/ builds as the component core.
cmake_minimum_required(VERSION 3.16)

set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../core")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

project(tremor_log)
