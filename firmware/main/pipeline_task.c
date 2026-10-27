/*
 * pipeline_task.c runs the converter and the detector. It is the only task
 * that calls the detector, because the detector's work buffers are static.
 *
 * The task takes every sensor message. It checks that the reading numbers
 * follow on and keeps each minute's sums for the gyroscope and the
 * accelerometer. It then gives the message to the rules in
 * core/pipeline.c, which follow the stretches, run the converter, and give
 * each complete window. The task runs det_run() on each window, times the run,
 * and sends the answer to the state task. When no sensor message comes for 2
 * seconds, it sends a sensor fault answer, and then one each second.
 *
 * When a stretch loses readings, the task asks the sensor task to end it
 * through the end queue. The task never waits on the state queue, and it
 * counts each message it drops.
 */

#include <math.h>
#include <stdint.h>
#include <string.h>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "detector.h"
#include "pipeline.h"
#include "tasks.h"
#include "window.h"

typedef struct {
    uint64_t n;
    double gyro_sum[3];
    double gyro_sum_sq[3];
    double accel_sum[3];
} minute_sums_t;

/* The counts from boot. */
typedef struct {
    uint32_t windows;
    uint32_t answer_drops;
    int64_t run_us_max;
    int64_t delay_us_max;
} pipeline_counts_t;

static sensor_msg_t s_msg;
static pipe_t s_pipe;
static float s_window[DET_WINDOW_LEN][DET_AXES];
static pipeline_counts_t s_counts;

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
             "gyro_sd_dps=%.4f,%.4f,%.4f accel_mean_counts=%.1f,%.1f,%.1f windows=%lu faults=%lu end_requests=%lu "
             "answer_drops=%lu rate_refused=%lu run_us_max=%lld delay_us_max=%lld stack_free=%lu",
             (unsigned long)minute, (unsigned long long)readings, (unsigned long)breaks, mean[0], mean[1], mean[2],
             sd[0], sd[1], sd[2], accel[0], accel[1], accel[2], (unsigned long)s_counts.windows,
             (unsigned long)s_pipe.faults, (unsigned long)s_pipe.end_requests, (unsigned long)s_counts.answer_drops,
             (unsigned long)s_pipe.rate_refused, (long long)s_counts.run_us_max, (long long)s_counts.delay_us_max,
             (unsigned long)uxTaskGetStackHighWaterMark(NULL));
}

static void send_state(const state_msg_t *msg)
{
    if (xQueueSend(g_state_queue, msg, 0) != pdTRUE) {
        s_counts.answer_drops++;
    }
}

static const char *reason_name(unsigned reason)
{
    switch (reason) {
    case PIPE_REASON_BREAK:
        return "break";
    case PIPE_REASON_MISSED_START:
        return "missed_start";
    case PIPE_REASON_RING_FULL:
        return "ring_full";
    default:
        return "none";
    }
}

/* request_end() asks the sensor task to end the stretch of the last request. */
static void request_end(void)
{
    uint32_t number = pipe_end_stretch(&s_pipe);
    xQueueOverwrite(g_end_queue, &number);
    usb_send("END_REQUEST stretch=%lu reason=%s", (unsigned long)number, reason_name(pipe_end_reason(&s_pipe)));
}

/* take_message() gives one sensor message to the pipe. */
static void take_message(const sensor_msg_t *m)
{
    pipe_part_t part = {
        .stretch = m->stretch,
        .flags = m->flags,
        .rate_uhz = m->rate_uhz,
        .stamp_us = m->stamp_us,
        .first_reading = m->first_reading,
        .count = m->count,
    };
    unsigned flags = pipe_part(&s_pipe, &part, esp_timer_get_time());
    if ((flags & PIPE_STRETCH) != 0) {
        state_msg_t msg = {
            .kind = STATE_MSG_STRETCH,
            .stretch = m->stretch,
            .rate_uhz = pipe_stretch(&s_pipe)->rate_uhz,
        };
        send_state(&msg);
    }
    if ((flags & PIPE_END) != 0) {
        request_end();
    }
    if ((flags & PIPE_DROP) == 0) {
        for (uint32_t i = 0; i < m->count; i++) {
            if ((pipe_push(&s_pipe, m->gyro_dps[i]) & PIPE_END) != 0) {
                request_end();
            }
        }
    }
}

/* run_windows() runs the detector on every complete window. */
static void run_windows(int64_t stamp_us)
{
    uint32_t number;
    int64_t time_us;
    while (pipe_window(&s_pipe, s_window, &number, &time_us)) {
        det_result_t r;
        int64_t start_us = esp_timer_get_time();
        det_run(s_window, &r);
        int64_t end_us = esp_timer_get_time();
        state_msg_t msg = {
            .kind = STATE_MSG_ANSWER,
            .stretch = pipe_stretch(&s_pipe)->number,
            .rate_uhz = pipe_stretch(&s_pipe)->rate_uhz,
            .has_window = true,
            .window = number,
            .code = (uint8_t)res_from_answer(number, &r),
            .prob = r.prob,
            .below = r.below,
            .peak_hz = r.peak_hz,
            .time_us = time_us,
            .run_us = end_us - start_us,
            .at_us = end_us,
            .delay_us = end_us - stamp_us,
        };
        s_counts.windows++;
        if (msg.run_us > s_counts.run_us_max) {
            s_counts.run_us_max = msg.run_us;
        }
        if (msg.delay_us > s_counts.delay_us_max) {
            s_counts.delay_us_max = msg.delay_us;
        }
        send_state(&msg);
    }
}

static void send_fault(void)
{
    int64_t now_us = esp_timer_get_time();
    state_msg_t msg = {
        .kind = STATE_MSG_ANSWER,
        .stretch = pipe_stretch(&s_pipe)->number,
        .rate_uhz = pipe_stretch(&s_pipe)->rate_uhz,
        .has_window = false,
        .window = 0,
        .code = (uint8_t)RES_SENSOR_FAULT,
        .time_us = now_us,
        .at_us = now_us,
    };
    send_state(&msg);
}

void pipeline_task(void *arg)
{
    (void)arg;
    send_task_line("pipeline");

    bool ok = det_init();
    usb_send("DETECTOR_INIT ok=%d", ok ? 1 : 0);
    if (!ok) {
        usb_send("PIPELINE_ERROR detector_init");
        vTaskDelete(NULL);
        return;
    }
    pipe_init(&s_pipe, esp_timer_get_time());

    uint64_t readings = 0;
    uint32_t breaks = 0;
    bool have_last = false;
    uint64_t next_first = 0;
    minute_sums_t sums;
    memset(&sums, 0, sizeof sums);
    uint32_t minute = 1;

    for (;;) {
        int64_t minute_us = (int64_t)minute * MINUTE_US;
        int64_t fault_us = pipe_next_fault_us(&s_pipe);
        int64_t due_us = fault_us < minute_us ? fault_us : minute_us;
        if (xQueueReceive(g_sensor_queue, &s_msg, ticks_until(due_us)) == pdTRUE) {
            if (have_last && s_msg.first_reading != next_first) {
                breaks++;
            }
            have_last = true;
            next_first = s_msg.first_reading + s_msg.count;
            readings += s_msg.count;
            add_message(&sums, &s_msg);

            take_message(&s_msg);
            run_windows(s_msg.stamp_us);
        }
        while (pipe_fault_due(&s_pipe, esp_timer_get_time())) {
            send_fault();
        }
        if (esp_timer_get_time() >= minute_us) {
            send_minute_line(minute, readings, breaks, &sums);
            memset(&sums, 0, sizeof sums);
            minute++;
        }
    }
}
