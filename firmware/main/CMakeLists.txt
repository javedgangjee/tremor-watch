# The five tasks, the face, the tone output, and the start code. The C files
# build with -Wall -Wextra -Werror. power.cpp includes XPowersLib's headers,
# and the fonts and icons in assets/ come from tools/gen_face_assets.py, so
# they build with ESP-IDF's own flags.
set(TASK_SOURCES
    main.c
    sensor_task.c
    pipeline_task.c
    state_task.c
    screen_task.c
    usb_task.c
    settings.c
    face_draw.c
    tone_out.c
)
set(ASSET_SOURCES
    assets/face_font_28.c
    assets/face_font_40.c
    assets/face_font_56.c
    assets/face_font_96.c
    assets/face_icons.c
)

idf_component_register(
    SRCS ${TASK_SOURCES} power.cpp ${ASSET_SOURCES}
    INCLUDE_DIRS "." "assets"
    PRIV_REQUIRES core esp_timer esp_driver_gpio esp_driver_i2c XPowersLib espressif__esp_lcd_touch nvs_flash spi_flash
        esp_driver_usb_serial_jtag espressif__esp_codec_dev)

set_source_files_properties(${TASK_SOURCES} PROPERTIES
    COMPILE_OPTIONS "-Wall;-Wextra;-Werror")

# The B line carries the table hash, which is DET_MODEL_SHA256 in
# core/detector_tables.h. Only detector.c may include that header, because it
# holds static arrays, so the configure step reads the hash from it and passes
# it in as TABLE_HASH. A new table hash runs the configure step again.
set(TABLES_HEADER "${CMAKE_CURRENT_LIST_DIR}/../../core/detector_tables.h")
file(STRINGS "${TABLES_HEADER}" hash_lines REGEX "^#define DET_MODEL_SHA256 ")
list(LENGTH hash_lines hash_line_count)
if(hash_line_count EQUAL 1)
    string(REGEX REPLACE "^#define DET_MODEL_SHA256 \"([^\"]*)\".*$" "\\1" table_hash "${hash_lines}")
else()
    set(table_hash "")
endif()
if(NOT table_hash MATCHES "^[0-9a-f]+$")
    message(FATAL_ERROR "core/detector_tables.h gives no DET_MODEL_SHA256 of 64 lower-case hexadecimal digits")
endif()
string(LENGTH "${table_hash}" table_hash_length)
if(NOT table_hash_length EQUAL 64)
    message(FATAL_ERROR "core/detector_tables.h gives no DET_MODEL_SHA256 of 64 lower-case hexadecimal digits")
endif()
target_compile_definitions(${COMPONENT_LIB} PRIVATE "TABLE_HASH=\"${table_hash}\"")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${TABLES_HEADER}")

# LVGL's fast memory option places some functions in IRAM twice, which GCC
# reports as a warning. Waveshare's 02_lvgl_demo_v9 turns these two warnings
# back from errors for the LVGL library, and this does the same.
idf_build_get_property(build_components BUILD_COMPONENTS)
if("lvgl__lvgl" IN_LIST build_components)
    idf_component_get_property(LVGL_LIB lvgl__lvgl COMPONENT_LIB)
    if(TARGET ${LVGL_LIB})
        target_compile_options(${LVGL_LIB} PRIVATE -Wno-error=attributes -Wno-error=cpp)
    endif()
endif()
