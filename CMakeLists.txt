# The laptop build of the shared C library, replay, and the C unit tests.
#
#     cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure
#
# core/CMakeLists.txt also registers core/ as an ESP-IDF component for the
# watch firmware in firmware/.

cmake_minimum_required(VERSION 3.20)
project(tremor_log C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

# The project's own C files build with these flags. Third-party code builds
# with -ffp-contract=off only, because it stays unchanged.
set(TREMOR_WARNINGS -Wall -Wextra -Werror -pedantic)
set(TREMOR_FP -ffp-contract=off)

enable_testing()

add_subdirectory(core)
add_subdirectory(tests)
