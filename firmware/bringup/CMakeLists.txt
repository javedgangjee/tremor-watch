# Rate program. It measures the QMI8658 reading rate against the 64-bit
# microsecond timer.
cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

project(bringup_rate)
