# The C unit tests. They use Unity and run through CTest.

add_library(unity STATIC unity/unity.c)
target_include_directories(unity PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/unity)
target_compile_definitions(unity PUBLIC UNITY_INCLUDE_DOUBLE)
target_compile_options(unity PRIVATE ${TREMOR_FP})

add_executable(test_detector detector/test_detector.c)
target_compile_options(test_detector PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_compile_definitions(test_detector PRIVATE "DETECTOR_TEST_DIR=\"${CMAKE_CURRENT_SOURCE_DIR}/detector\"")
target_link_libraries(test_detector PRIVATE tremor_core unity)
add_test(NAME test_detector COMMAND test_detector)
