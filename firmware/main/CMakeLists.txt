# The five tasks and the start code. The C files build with -Wall -Wextra
# -Werror. power.cpp includes XPowersLib's headers, so it builds with
# ESP-IDF's own flags.
set(TASK_SOURCES
    main.c
    sensor_task.c
    pipeline_task.c
    state_task.c
    screen_task.c
    usb_task.c
)

idf_component_register(
    SRCS ${TASK_SOURCES} power.cpp
    INCLUDE_DIRS "."
    PRIV_REQUIRES core esp_timer esp_driver_gpio esp_driver_i2c XPowersLib espressif__esp_lcd_touch)

set_source_files_properties(${TASK_SOURCES} PROPERTIES
    COMPILE_OPTIONS "-Wall;-Wextra;-Werror")

# LVGL's fast memory option puts some functions in IRAM twice, which GCC
# reports as a warning. Waveshare's 02_lvgl_demo_v9 turns these two warnings
# back from errors for the LVGL library, and this does the same.
idf_build_get_property(build_components BUILD_COMPONENTS)
if("lvgl__lvgl" IN_LIST build_components)
    idf_component_get_property(LVGL_LIB lvgl__lvgl COMPONENT_LIB)
    if(TARGET ${LVGL_LIB})
        target_compile_options(${LVGL_LIB} PRIVATE -Wno-error=attributes -Wno-error=cpp)
    endif()
endif()
