/*
 * main.c starts the settings store, makes the queues, sets up the shared I2C
 * bus, reads the power chip once, and starts the five tasks. It calls no LVGL
 * function, because only the screen task uses LVGL.
 */

#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_intr_alloc.h"
#include "freertos/FreeRTOS.h"
#include "freertos/idf_additions.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include "bsp/esp-bsp.h"
#include "power.h"
#include "tasks.h"

/* The queue lengths. A sensor message carries about 100 milliseconds of
 * readings, so the sensor queue holds about 3 seconds. */
#define SENSOR_QUEUE_LEN 32
#define LINE_QUEUE_LEN 48
#define SCREEN_QUEUE_LEN 4
#define STATE_QUEUE_LEN 8
/* The record queue holds about 3 seconds of burst parts. It, the line queue,
 * the sensor queue, and the screen queue live in PSRAM, because each display
 * transfer needs a block of about 82 KB of internal memory, which they would
 * break up. */
#define RECORD_QUEUE_LEN 32

/* The stack sizes in bytes. */
#define SENSOR_STACK 6144
#define PIPELINE_STACK 4096
#define STATE_STACK 4096
#define SCREEN_STACK 4096
#define USB_STACK 4096

/* The screen task's on_touch() relies on every flash call coming from the
 * core of the GPIO interrupt. app_main() installs that interrupt, and the
 * state task makes every settings store call. */
#if !CONFIG_ESP_MAIN_TASK_AFFINITY_CPU0
#error "app_main must run on core 0, the state task's core"
#endif
_Static_assert(STATE_CORE == 0, "the state task must run on the GPIO interrupt's core");

QueueHandle_t g_sensor_queue;
QueueHandle_t g_line_queue;
QueueHandle_t g_screen_queue;
QueueHandle_t g_state_queue;
QueueHandle_t g_end_queue;
QueueHandle_t g_record_queue;

static void send_power_line(void)
{
    esp_err_t err = power_init();
    power_info_t info = {0};
    if (err == ESP_OK) {
        err = power_read(&info);
    }
    if (err != ESP_OK) {
        usb_send("POWER pmu=error err=%s", esp_err_to_name(err));
        return;
    }
    usb_send("POWER pmu=ok vbus=%d battery=%d battery_mv=%u battery_percent=%d", info.vbus_in ? 1 : 0,
             info.battery_in ? 1 : 0, (unsigned)info.battery_mv, info.battery_percent);
}

/* start_settings() starts the settings store before any task reads it. It
 * erases the store and starts it again only when ESP-IDF asks for that, as
 * ESP-IDF's examples do. */
static void start_settings(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

void app_main(void)
{
    start_settings();

    /* The line queue comes first, so every line waits in it until the USB
     * task runs. */
    g_line_queue = xQueueCreateWithCaps(LINE_QUEUE_LEN, sizeof(line_t), MALLOC_CAP_SPIRAM);
    g_sensor_queue = xQueueCreateWithCaps(SENSOR_QUEUE_LEN, sizeof(sensor_msg_t), MALLOC_CAP_SPIRAM);
    g_screen_queue = xQueueCreateWithCaps(SCREEN_QUEUE_LEN, sizeof(view_t), MALLOC_CAP_SPIRAM);
    g_state_queue = xQueueCreate(STATE_QUEUE_LEN, sizeof(state_msg_t));
    g_end_queue = xQueueCreate(1, sizeof(uint32_t));
    g_record_queue = xQueueCreateWithCaps(RECORD_QUEUE_LEN, sizeof(record_msg_t), MALLOC_CAP_SPIRAM);
    ESP_ERROR_CHECK(g_line_queue != NULL && g_sensor_queue != NULL && g_screen_queue != NULL &&
                            g_state_queue != NULL && g_end_queue != NULL && g_record_queue != NULL
                        ? ESP_OK
                        : ESP_ERR_NO_MEM);

    ESP_ERROR_CHECK(bsp_i2c_init());

    /* The touch driver and the sensor task both add GPIO interrupts. The
     * service goes in here, before either task starts. It runs from IRAM, so
     * the sensor's INT1 stamp stays on time while the settings store writes
     * to flash with the cache off. A stamp more than half a reading late would
     * end a stretch. Every handler on it must then be safe with the cache off.
     * The sensor task's on_int1() is, and the screen task wraps the touch
     * handler in on_touch(). The service runs on this core, which is core 0. */
    esp_err_t err = gpio_install_isr_service(ESP_INTR_FLAG_IRAM);
    ESP_ERROR_CHECK(err == ESP_ERR_INVALID_STATE ? ESP_OK : err);

    send_power_line();

    xTaskCreatePinnedToCore(usb_task, "usb", USB_STACK, NULL, USB_PRIORITY, NULL, USB_CORE);
    xTaskCreatePinnedToCore(sensor_task, "sensor", SENSOR_STACK, NULL, SENSOR_PRIORITY, NULL, SENSOR_CORE);
    xTaskCreatePinnedToCore(pipeline_task, "pipeline", PIPELINE_STACK, NULL, PIPELINE_PRIORITY, NULL, PIPELINE_CORE);
    xTaskCreatePinnedToCore(state_task, "state", STATE_STACK, NULL, STATE_PRIORITY, NULL, STATE_CORE);
    xTaskCreatePinnedToCore(screen_task, "screen", SCREEN_STACK, NULL, SCREEN_PRIORITY, NULL, SCREEN_CORE);
}
