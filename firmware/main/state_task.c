/*
 * state_task.c owns the current state. In this feature it sends the screen
 * task the uptime once a second. Feature 8 adds the face state, the session
 * share, and the doses.
 */

#include <stdint.h>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "tasks.h"

void state_task(void *arg)
{
    (void)arg;
    send_task_line("state");

    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        xTaskDelayUntil(&wake, pdMS_TO_TICKS(1000));
        screen_msg_t msg = {.uptime_s = (uint32_t)(esp_timer_get_time() / 1000000)};
        xQueueSend(g_screen_queue, &msg, 0);
    }
}
