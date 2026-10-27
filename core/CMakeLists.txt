# The project's own sources. Both builds use this one list, so a new file gets
# the same flags on the laptop and on the watch.
set(TREMOR_SOURCES
    detector.c
    reading_time.c
    converter.c
    window.c
    share.c
    face.c
    dose.c
    imu_units.c
    pipeline.c
    session.c
    record.c
    look.c
    screens.c
    view.c
    tone.c
)

# On the watch, ESP-IDF builds core/ as the component core and returns before
# the laptop part. The flags match the laptop build in the root CMakeLists.txt.
# replay is a laptop program only.
if(ESP_PLATFORM)
    idf_component_register(
        SRCS ${TREMOR_SOURCES} kissfft/kiss_fft.c kissfft/kiss_fftr.c
        INCLUDE_DIRS ".")
    target_compile_options(${COMPONENT_LIB} PRIVATE
        -ffp-contract=off
        "-DKISS_FFT_MALLOC(n)=((void *)0)"
        "-DKISS_FFT_FREE(p)=((void)0)"
    )
    set_source_files_properties(${TREMOR_SOURCES} PROPERTIES
        COMPILE_OPTIONS "-Wall;-Wextra;-Werror;-pedantic")
    # ESP-IDF wraps stdio.h with #include_next, which -pedantic reports as an
    # error. Marking the wrapper folder as a system folder keeps -pedantic for
    # the project's own code.
    idf_component_get_property(libc_dir esp_libc COMPONENT_DIR)
    target_compile_options(${COMPONENT_LIB} PRIVATE -isystem "${libc_dir}/platform_include")
    return()
endif()

# tremor_core is the shared C library. KISS FFT's heap calls are no-ops, so
# nothing in the library allocates memory.
add_library(tremor_core STATIC ${TREMOR_SOURCES} kissfft/kiss_fft.c kissfft/kiss_fftr.c)
target_include_directories(tremor_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(tremor_core PRIVATE ${TREMOR_FP})
# CMake drops function-style macros from compile definitions, so these two
# go in as compiler options.
target_compile_options(tremor_core PRIVATE
    "-DKISS_FFT_MALLOC(n)=((void *)0)"
    "-DKISS_FFT_FREE(p)=((void)0)"
)
set_source_files_properties(${TREMOR_SOURCES} PROPERTIES COMPILE_OPTIONS "${TREMOR_WARNINGS}")
target_link_libraries(tremor_core PUBLIC m)

add_executable(replay replay.c)
target_compile_options(replay PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(replay PRIVATE tremor_core)
