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

add_executable(test_imu_units imu_units/test_imu_units.c)
target_compile_options(test_imu_units PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_imu_units PRIVATE tremor_core unity)
add_test(NAME test_imu_units COMMAND test_imu_units)

add_executable(test_pipeline pipeline/test_pipeline.c)
target_compile_options(test_pipeline PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_pipeline PRIVATE tremor_core unity)
add_test(NAME test_pipeline COMMAND test_pipeline)

add_executable(test_session session/test_session.c)
target_compile_options(test_session PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_session PRIVATE tremor_core unity)
add_test(NAME test_session COMMAND test_session)

add_executable(test_record record/test_record.c)
target_compile_options(test_record PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_record PRIVATE tremor_core unity)
add_test(NAME test_record COMMAND test_record)

add_executable(test_look look/test_look.c)
target_compile_options(test_look PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_look PRIVATE tremor_core unity)
add_test(NAME test_look COMMAND test_look)

add_executable(test_screens screens/test_screens.c)
target_compile_options(test_screens PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_screens PRIVATE tremor_core unity)
add_test(NAME test_screens COMMAND test_screens)

add_executable(test_view view/test_view.c)
target_compile_options(test_view PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_view PRIVATE tremor_core unity)
add_test(NAME test_view COMMAND test_view)

add_executable(test_tone tone/test_tone.c)
target_compile_options(test_tone PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(test_tone PRIVATE tremor_core unity)
add_test(NAME test_tone COMMAND test_tone)
