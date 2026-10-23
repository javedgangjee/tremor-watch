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

add_executable(test_reading_time reading_time/test_reading_time.c)
target_compile_options(test_reading_time PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_reading_time PRIVATE tremor_core unity)
add_test(NAME test_reading_time COMMAND test_reading_time)

add_executable(test_converter converter/test_converter.c)
target_compile_options(test_converter PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_compile_definitions(test_converter PRIVATE "CONVERTER_TEST_DIR=\"${CMAKE_CURRENT_SOURCE_DIR}/converter\"")
target_link_libraries(test_converter PRIVATE tremor_core unity)
add_test(NAME test_converter COMMAND test_converter)

add_executable(test_window window/test_window.c)
target_compile_options(test_window PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_window PRIVATE tremor_core unity)
add_test(NAME test_window COMMAND test_window)

add_executable(test_share share/test_share.c)
target_compile_options(test_share PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_share PRIVATE tremor_core unity)
add_test(NAME test_share COMMAND test_share)

add_executable(test_face face/test_face.c)
target_compile_options(test_face PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_face PRIVATE tremor_core unity)
add_test(NAME test_face COMMAND test_face)

add_executable(test_dose dose/test_dose.c)
target_compile_options(test_dose PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_dose PRIVATE tremor_core unity)
add_test(NAME test_dose COMMAND test_dose)

add_executable(test_response response/test_response.c)
target_compile_options(test_response PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_response PRIVATE tremor_core unity)
add_test(NAME test_response COMMAND test_response)
