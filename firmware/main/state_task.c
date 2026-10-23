/*
 * state_task.c owns the current state. It holds the face state, the session
 * share, the dose schedule, and the doses taken, and its rules live in
 * core/session.c.
 *
 * The task takes each new stretch and each answer from the pipeline task and
 * writes a GAP or an ANSWER line for it, then a FACE line when the shown state
 * changes. It ticks the doses once a second, and it sends the screen task the
 * uptime and the shown state once a second and at each change. It never waits
 * on the screen queue, and it counts each message it drops.
 *
 * In this feature the dose clock and the schedule stay unset, so no dose
 * becomes due. Feature 9 adds the commands that set them.
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "session.h"
#include "tasks.h"

#define SECOND_TICKS pdMS_TO_TICKS(1000)

static sess_t s_sess;
static uint32_t s_screen_drops;

static void send_screen(void)
{
    screen_msg_t msg = {
        .uptime_s = (uint32_t)(esp_timer_get_time() / 1000000),
        .face = (uint8_t)face_shown(&s_sess.face),
    };
    if (xQueueSend(g_screen_queue, &msg, 0) != pdTRUE) {
        s_screen_drops++;
    }
}

/* after_call() sends the FACE line and a screen message when the shown state
 * changed. */
static void after_call(unsigned flags)
{
    if ((flags & SESS_FACE_CHANGED) == 0) {
        return;
    }
    usb_send("FACE at_us=%lld state=%d", (long long)esp_timer_get_time(), (int)face_shown(&s_sess.face));
    send_screen();
}

static void take_stretch(const state_msg_t *m)
{
    unsigned flags = sess_stretch(&s_sess, m->stretch);
    if (m->stretch > 0) {
        usb_send("GAP stretch=%lu changed=%d", (unsigned long)m->stretch, (flags & SESS_FACE_CHANGED) != 0 ? 1 : 0);
    }
    after_call(flags);
}

static void take_answer(const state_msg_t *m)
{
    unsigned flags = sess_answer(&s_sess, m->has_window, m->window, (res_code_t)m->code, m->time_us);
    char window[12] = "none";
    char prob[32] = "none";
    char below[32] = "none";
    char peak[24] = "none";
    if (m->has_window) {
        snprintf(window, sizeof window, "%lu", (unsigned long)m->window);
        snprintf(prob, sizeof prob, "%.17g", m->prob);
        snprintf(below, sizeof below, "%.17g", m->below);
        snprintf(peak, sizeof peak, "%.9g", (double)m->peak_hz);
    }
    usb_send("ANSWER stretch=%lu window=%s code=%u prob=%s below=%s peak=%s time_us=%lld at_us=%lld run_us=%lld "
             "delay_us=%lld counted=%d face=%d",
             (unsigned long)m->stretch, window, (unsigned)m->code, prob, below, peak, (long long)m->time_us,
             (long long)m->at_us, (long long)m->run_us, (long long)m->delay_us,
             (flags & SESS_COUNTED) != 0 ? 1 : 0, (int)face_shown(&s_sess.face));
    after_call(flags);
}

static void send_minute_line(uint32_t minute)
{
    const share_t *sh = &s_sess.share;
    const uint32_t *a = s_sess.answers;
    uint32_t total = 0;
    for (int code = 0; code < RES_COUNT; code++) {
        total += a[code];
    }
    char share[32] = "none";
    double percent;
    if (share_percent(sh, &percent)) {
        snprintf(share, sizeof share, "%.6f", percent);
    }
    usb_send("STATE_MINUTE minute=%lu answers=%lu tremor=%lu no_tremor=%lu moving=%lu warming=%lu fault=%lu "
             "share_tremor=%lu share_still=%lu share_moving=%lu share=%s face=%d face_changes=%lu gaps=%lu "
             "blocks=%lu screen_drops=%lu stack_free=%lu",
             (unsigned long)minute, (unsigned long)total, (unsigned long)a[RES_TREMOR],
             (unsigned long)a[RES_NO_TREMOR], (unsigned long)a[RES_ARM_MOVING], (unsigned long)a[RES_WARMING_UP],
             (unsigned long)a[RES_SENSOR_FAULT], (unsigned long)sh->tremor,
             (unsigned long)(sh->tremor + sh->no_tremor), (unsigned long)sh->moving, share,
             (int)face_shown(&s_sess.face), (unsigned long)s_sess.face_changes, (unsigned long)s_sess.gaps,
             (unsigned long)share_block_count(sh), (unsigned long)s_screen_drops,
             (unsigned long)uxTaskGetStackHighWaterMark(NULL));
}

void state_task(void *arg)
{
    (void)arg;
    send_task_line("state");
    sess_init(&s_sess, esp_timer_get_time());

    TickType_t next_second = xTaskGetTickCount() + SECOND_TICKS;
    uint32_t minute = 1;
    state_msg_t msg;
    for (;;) {
        TickType_t now = xTaskGetTickCount();
        TickType_t wait = (TickType_t)(next_second - now) <= SECOND_TICKS ? next_second - now : 0;
        if (xQueueReceive(g_state_queue, &msg, wait) == pdTRUE) {
            if (msg.kind == STATE_MSG_STRETCH) {
                take_stretch(&msg);
            } else {
                take_answer(&msg);
            }
        }
        if ((TickType_t)(xTaskGetTickCount() - next_second) < (TickType_t)0x80000000u) {
            next_second += SECOND_TICKS;
            unsigned flags = sess_tick(&s_sess, esp_timer_get_time());
            if ((flags & SESS_TONE) != 0) {
                usb_send("TONE");
            }
            after_call(flags);
            send_screen();
            if (esp_timer_get_time() >= (int64_t)minute * MINUTE_US) {
                send_minute_line(minute);
                minute++;
            }
        }
    }
}
