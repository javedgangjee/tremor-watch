/*
 * pipeline_task.c takes every sensor message. In this feature it checks that
 * the reading numbers follow on and keeps each minute's sums for the
 * gyroscope and the accelerometer. Feature 8 adds the converter and the
 * detector, and this task is then the only task that calls the detector.
 */

#include <math.h>
#include <stdint.h>
#include <string.h>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#include "tasks.h"

typedef struct {
    uint64_t n;
    double gyro_sum[3];
    double gyro_sum_sq[3];
    double accel_sum[3];
} minute_sums_t;

static sensor_msg_t s_msg;

static TickType_t ticks_until(int64_t due_us)
{
    int64_t wait_us = due_us - esp_timer_get_time();
    if (wait_us <= 0) {
        return 0;
    }
    return pdMS_TO_TICKS(wait_us / 1000) + 1;
}

static void add_message(minute_sums_t *sums, const sensor_msg_t *m)
{
    for (uint32_t i = 0; i < m->count; i++) {
        for (int axis = 0; axis < 3; axis++) {
            double g = (double)m->gyro_dps[i][axis];
            sums->gyro_sum[axis] += g;
            sums->gyro_sum_sq[axis] += g * g;
            sums->accel_sum[axis] += (double)m->raw[i][axis];
        }
    }
    sums->n += m->count;
}

static void send_minute_line(uint32_t minute, uint64_t readings, uint32_t breaks, const minute_sums_t *sums)
{
    double n = sums->n > 0 ? (double)sums->n : 1.0;
    double mean[3];
    double sd[3];
    double accel[3];
    for (int axis = 0; axis < 3; axis++) {
        mean[axis] = sums->gyro_sum[axis] / n;
        double var = sums->gyro_sum_sq[axis] / n - mean[axis] * mean[axis];
        sd[axis] = var > 0.0 ? sqrt(var) : 0.0;
        accel[axis] = sums->accel_sum[axis] / n;
    }
    usb_send("PIPELINE_MINUTE minute=%lu readings=%llu breaks=%lu gyro_mean_dps=%.4f,%.4f,%.4f "
             "gyro_sd_dps=%.4f,%.4f,%.4f accel_mean_counts=%.1f,%.1f,%.1f",
             (unsigned long)minute, (unsigned long long)readings, (unsigned long)breaks, mean[0], mean[1], mean[2],
             sd[0], sd[1], sd[2], accel[0], accel[1], accel[2]);
}

void pipeline_task(void *arg)
{
    (void)arg;
    send_task_line("pipeline");

    uint64_t readings = 0;
    uint32_t breaks = 0;
    bool have_last = false;
    uint64_t next_first = 0;
    minute_sums_t sums;
    memset(&sums, 0, sizeof sums);
    uint32_t minute = 1;

    for (;;) {
        int64_t due_us = (int64_t)minute * MINUTE_US;
        if (xQueueReceive(g_sensor_queue, &s_msg, ticks_until(due_us)) == pdTRUE) {
            if (have_last && s_msg.first_reading != next_first) {
                breaks++;
            }
            have_last = true;
            next_first = s_msg.first_reading + s_msg.count;
            readings += s_msg.count;
            add_message(&sums, &s_msg);
        }
        if (esp_timer_get_time() >= due_us) {
            send_minute_line(minute, readings, breaks, &sums);
            memset(&sums, 0, sizeof sums);
            minute++;
        }
    }
}
