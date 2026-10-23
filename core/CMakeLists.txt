# tremor_core is the shared C library. KISS FFT builds into it with its heap
# calls turned into no-ops, so nothing in the library allocates memory.

add_library(tremor_core STATIC
    detector.c
    reading_time.c
    converter.c
    kissfft/kiss_fft.c
    kissfft/kiss_fftr.c
)
target_include_directories(tremor_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(tremor_core PRIVATE ${TREMOR_FP})
# CMake drops function-style macros from compile definitions, so these two
# go in as compiler options.
target_compile_options(tremor_core PRIVATE
    "-DKISS_FFT_MALLOC(n)=((void *)0)"
    "-DKISS_FFT_FREE(p)=((void)0)"
)
set_source_files_properties(detector.c reading_time.c converter.c PROPERTIES COMPILE_OPTIONS "${TREMOR_WARNINGS}")
target_link_libraries(tremor_core PUBLIC m)

add_executable(replay replay.c)
target_compile_options(replay PRIVATE ${TREMOR_WARNINGS} ${TREMOR_FP})
target_link_libraries(replay PRIVATE tremor_core)
