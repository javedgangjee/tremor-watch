/*
 * usb_task.c owns the serial port over USB. It is the only file in
 * firmware/main that writes to the port. The other tasks put lines on the
 * line queue with usb_send(), never wait on it, and count the lines they drop.
 *
 * Feature 9 adds the recording lines and the laptop's commands.
 */

#include <inttypes.h>
#include <stdarg.h>
#include <stdio.h>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "tasks.h"

atomic_uint g_line_drops;

bool usb_send(const char *fmt, ...)
{
    line_t line;
    va_list args;
    va_start(args, fmt);
    vsnprintf(line.text, sizeof line.text, fmt, args);
    va_end(args);
    if (xQueueSend(g_line_queue, &line, 0) != pdTRUE) {
        atomic_fetch_add(&g_line_drops, 1u);
        return false;
    }
    return true;
}

void send_task_line(const char *name)
{
    usb_send("TASK name=%s core=%d priority=%u", name, (int)xPortGetCoreID(), (unsigned)uxTaskPriorityGet(NULL));
}

/* ticks_until() gives the ticks from now until the uptime due_us, at least 1. */
static TickType_t ticks_until(int64_t due_us)
{
    int64_t wait_us = due_us - esp_timer_get_time();
    if (wait_us <= 0) {
        return 0;
    }
    return pdMS_TO_TICKS(wait_us / 1000) + 1;
}

void usb_task(void *arg)
{
    (void)arg;
    printf("START uptime_us=%" PRId64 "\n", esp_timer_get_time());
    send_task_line("usb");

    uint32_t minute = 1;
    line_t line;
    for (;;) {
        int64_t due_us = (int64_t)minute * MINUTE_US;
        if (xQueueReceive(g_line_queue, &line, ticks_until(due_us)) == pdTRUE) {
            printf("%s\n", line.text);
        }
        if (esp_timer_get_time() >= due_us) {
            printf("USB_MINUTE minute=%" PRIu32 " line_drops=%u\n", minute, atomic_load(&g_line_drops));
            minute++;
        }
    }
}
