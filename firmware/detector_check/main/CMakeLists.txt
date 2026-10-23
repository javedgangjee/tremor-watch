# The check program. tests/firmware/windows_bin.py turns the saved windows
# into little-endian 32-bit floats at build time, and the program embeds them.
idf_component_register(
    SRCS detector_check.c
    PRIV_REQUIRES core esp_timer esp_rom)

set_source_files_properties(detector_check.c PROPERTIES COMPILE_OPTIONS "-Wall;-Wextra;-Werror")

set(repo "${CMAKE_CURRENT_LIST_DIR}/../../..")
set(windows_csv "${repo}/tests/detector/windows.csv")
set(windows_script "${repo}/tests/firmware/windows_bin.py")
set(windows_bin "${CMAKE_CURRENT_BINARY_DIR}/windows.bin")
idf_build_get_property(python PYTHON)

add_custom_command(
    OUTPUT "${windows_bin}"
    COMMAND "${python}" "${windows_script}" --csv "${windows_csv}" --out "${windows_bin}"
    DEPENDS "${windows_csv}" "${windows_script}"
    VERBATIM)
add_custom_target(detector_check_windows DEPENDS "${windows_bin}")
target_add_binary_data(${COMPONENT_LIB} "${windows_bin}" BINARY DEPENDS detector_check_windows)
