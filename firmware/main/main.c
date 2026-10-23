/*
 * main.c starts the watch. It sets up the shared I2C bus and the queues,
 * reads the power chip once, and starts the five tasks. It calls no LVGL
 * function, because only the screen task uses LVGL.
 */

#include "driver/gpio.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "bsp/esp-bsp.h"
#include "power.h"
#include "tasks.h"

/* The queue lengths. A sensor message carries about 100 milliseconds of
 * readings, so the sensor queue holds about 3 seconds. */
#define SENSOR_QUEUE_LEN 32
#define LINE_QUEUE_LEN 48
#define SCREEN_QUEUE_LEN 4

/* The stack sizes in bytes. */
#define SENSOR_STACK 6144
#define PIPELINE_STACK 4096
#define STATE_STACK 3072
#define SCREEN_STACK 4096
#define USB_STACK 4096

QueueHandle_t g_sensor_queue;
QueueHandle_t g_line_queue;
QueueHandle_t g_screen_queue;

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

void app_main(void)
{
    /* The line queue comes first, so every line waits in it until the USB
     * task runs. */
    g_line_queue = xQueueCreate(LINE_QUEUE_LEN, sizeof(line_t));
    g_sensor_queue = xQueueCreate(SENSOR_QUEUE_LEN, sizeof(sensor_msg_t));
    g_screen_queue = xQueueCreate(SCREEN_QUEUE_LEN, sizeof(screen_msg_t));
    ESP_ERROR_CHECK(g_line_queue != NULL && g_sensor_queue != NULL && g_screen_queue != NULL ? ESP_OK
                                                                                              : ESP_ERR_NO_MEM);

    ESP_ERROR_CHECK(bsp_i2c_init());

    /* The touch driver and the sensor task both add GPIO interrupts. The
     * service goes in here, before either task starts. */
    esp_err_t err = gpio_install_isr_service(0);
    ESP_ERROR_CHECK(err == ESP_ERR_INVALID_STATE ? ESP_OK : err);

    send_power_line();

    xTaskCreatePinnedToCore(usb_task, "usb", USB_STACK, NULL, USB_PRIORITY, NULL, 0);
    xTaskCreatePinnedToCore(sensor_task, "sensor", SENSOR_STACK, NULL, SENSOR_PRIORITY, NULL, 1);
    xTaskCreatePinnedToCore(pipeline_task, "pipeline", PIPELINE_STACK, NULL, PIPELINE_PRIORITY, NULL, 1);
    xTaskCreatePinnedToCore(state_task, "state", STATE_STACK, NULL, STATE_PRIORITY, NULL, 0);
    xTaskCreatePinnedToCore(screen_task, "screen", SCREEN_STACK, NULL, SCREEN_PRIORITY, NULL, 0);
}
