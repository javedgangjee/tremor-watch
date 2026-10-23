# The chip check of the saved windows. It runs the C detector from core/ on
# the 322 windows in tests/detector/windows.csv, twice, and prints each
# result for tests/firmware/chip_windows.py to judge on the laptop. The
# windows take 1,545,600 bytes, so they stay out of the watch firmware.
cmake_minimum_required(VERSION 3.16)

set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../../core")
# Only main and what it needs are built.
set(COMPONENTS main)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

project(detector_check)
