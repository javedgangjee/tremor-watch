/*
 * state_task.c owns the current state. It holds the face state, the session
 * share, the dose schedule, and the doses taken, and its rules live in
 * core/session.c.
 *
 * The task takes each new stretch and each answer from the pipeline task and
 * writes a GAP line, or an ANSWER line and the W line of the recording. When
 * the shown state changes, it writes a FACE line and the F line. It ticks the
 * doses once a second, and it sends the screen task the uptime and the shown
 * state once a second and at each change. It never waits on the screen
 * queue, and it counts each message it drops.
 *
 * At start the task loads the dose schedule and the tone setting from the
 * settings store. It applies the laptop's commands that the USB task sends,
 * writes a line for each, and answers each with an A line. The CLOCK command
 * sets the dose clock, which lives in memory only, so a restart leaves it
 * unset until the next CLOCK command. Until then no dose becomes due.
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "record.h"
#include "session.h"
#include "settings.h"
#include "tasks.h"

#define SECOND_TICKS pdMS_TO_TICKS(1000)

static sess_t s_sess;
static uint32_t s_screen_drops;
static bool s_tone_on;

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

/* after_call() sends the FACE line, the F line, and a screen message when the
 * shown state changed. Both lines carry the same timer value. */
static void after_call(unsigned flags)
{
    if ((flags & SESS_FACE_CHANGED) == 0) {
        return;
    }
    int64_t now_us = esp_timer_get_time();
    face_state_t shown = face_shown(&s_sess.face);
    usb_send("FACE at_us=%lld state=%d", (long long)now_us, (int)shown);
    char line[REC_LINE_MAX];
    if (rec_face(line, sizeof line, now_us, shown) > 0) {
        usb_send("%s", line);
    }
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
    char line[REC_LINE_MAX];
    if (rec_window(line, sizeof line, m->stretch, m->has_window, m->window, (res_code_t)m->code, m->prob, m->below,
            m->peak_hz) > 0) {
        usb_send("%s", line);
    }
    after_call(flags);
}

/* reply() sends the A line of a command. */
static void reply(rec_cmd_t command, rec_result_t result)
{
    char line[REC_LINE_MAX];
    if (rec_reply(line, sizeof line, command, result) > 0) {
        usb_send("%s", line);
    }
}

/* send_settings() sends the SETTINGS line. The name goes last, because it may
 * be empty. */
static void send_settings(const char *source, const char *store)
{
    const dose_schedule_t *s = &s_sess.dose.schedule;
    char times[DOSE_MAX_TIMES * 5 + 1] = "none";
    size_t used = 0;
    for (uint8_t i = 0; i < s->count; i++) {
        used += (size_t)snprintf(times + used, sizeof times - used, "%s%u", i == 0 ? "" : ",",
                                 (unsigned)s->minutes[i]);
    }
    usb_send("SETTINGS source=%s store=%s tone=%d times=%s name=%s", source, store, s_tone_on ? 1 : 0, times,
             s->name);
}

/* load_settings() loads the schedule and the tone setting at start. A schedule
 * that dose_set_schedule() refuses counts as a store error, and the schedule
 * stays off. */
static void load_settings(void)
{
    settings_t settings;
    settings_status_t status = settings_load(&settings);
    s_tone_on = settings.tone_on;
    if (status == SETTINGS_OK && !dose_set_schedule(&s_sess.dose, &settings.schedule, esp_timer_get_time())) {
        status = SETTINGS_ERROR;
    }
    const char *store = status == SETTINGS_OK ? "ok" : status == SETTINGS_EMPTY ? "empty" : "error";
    send_settings("boot", store);
}

/* take_command() applies one command from the USB task. Each command's own
 * line goes before its A line. */
static void take_command(const state_msg_t *m)
{
    const rec_command_t *c = &m->command;
    switch (c->kind) {
    case REC_CMD_CLOCK: {
        int64_t offset_us = rec_clock_offset_us(c->utc_us, c->offset_min, m->at_us);
        dose_set_clock(&s_sess.dose, offset_us, esp_timer_get_time());
        usb_send("CLOCK at_us=%lld offset_us=%lld local_us=%lld", (long long)m->at_us, (long long)offset_us,
                 (long long)(m->at_us + offset_us));
        reply(REC_CMD_CLOCK, REC_DONE);
        break;
    }
    case REC_CMD_SCHEDULE: {
        if (!dose_set_schedule(&s_sess.dose, &c->schedule, esp_timer_get_time())) {
            reply(REC_CMD_SCHEDULE, REC_REFUSED);
            break;
        }
        bool stored = settings_save_schedule(&s_sess.dose.schedule);
        send_settings("command", stored ? "ok" : "error");
        reply(REC_CMD_SCHEDULE, stored ? REC_DONE : REC_NOT_STORED);
        break;
    }
    case REC_CMD_SESSION: {
        face_state_t before = face_shown(&s_sess.face);
        int64_t now_us = esp_timer_get_time();
        sess_new_session(&s_sess, now_us);
        bool changed = face_shown(&s_sess.face) != before;
        usb_send("SESSION at_us=%lld changed=%d", (long long)now_us, changed ? 1 : 0);
        after_call(changed ? SESS_FACE_CHANGED : 0u);
        reply(REC_CMD_SESSION, REC_DONE);
        break;
    }
    case REC_CMD_TONE: {
        s_tone_on = c->tone_on;
        bool stored = settings_save_tone(s_tone_on);
        send_settings("command", stored ? "ok" : "error");
        reply(REC_CMD_TONE, stored ? REC_DONE : REC_NOT_STORED);
        break;
    }
    default:
        reply(c->kind, REC_UNKNOWN);
        break;
    }
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
             "blocks=%lu screen_drops=%lu stack_free=%lu clock=%d schedule=%u due=%d doses=%lu tone=%d",
             (unsigned long)minute, (unsigned long)total, (unsigned long)a[RES_TREMOR],
             (unsigned long)a[RES_NO_TREMOR], (unsigned long)a[RES_ARM_MOVING], (unsigned long)a[RES_WARMING_UP],
             (unsigned long)a[RES_SENSOR_FAULT], (unsigned long)sh->tremor,
             (unsigned long)(sh->tremor + sh->no_tremor), (unsigned long)sh->moving, share,
             (int)face_shown(&s_sess.face), (unsigned long)s_sess.face_changes, (unsigned long)s_sess.gaps,
             (unsigned long)share_block_count(sh), (unsigned long)s_screen_drops,
             (unsigned long)uxTaskGetStackHighWaterMark(NULL), s_sess.dose.clock_set ? 1 : 0,
             (unsigned)s_sess.dose.schedule.count, dose_is_due(&s_sess.dose) ? 1 : 0,
             (unsigned long)dose_count(&s_sess.dose), s_tone_on ? 1 : 0);
}

void state_task(void *arg)
{
    (void)arg;
    send_task_line("state");
    sess_init(&s_sess, esp_timer_get_time());
    load_settings();

    TickType_t next_second = xTaskGetTickCount() + SECOND_TICKS;
    uint32_t minute = 1;
    state_msg_t msg;
    for (;;) {
        TickType_t now = xTaskGetTickCount();
        TickType_t wait = (TickType_t)(next_second - now) <= SECOND_TICKS ? next_second - now : 0;
        if (xQueueReceive(g_state_queue, &msg, wait) == pdTRUE) {
            if (msg.kind == STATE_MSG_STRETCH) {
                take_stretch(&msg);
            } else if (msg.kind == STATE_MSG_COMMAND) {
                take_command(&msg);
            } else {
                take_answer(&msg);
            }
        }
        if ((TickType_t)(xTaskGetTickCount() - next_second) < (TickType_t)0x80000000u) {
            next_second += SECOND_TICKS;
            unsigned flags = sess_tick(&s_sess, esp_timer_get_time());
            if ((flags & SESS_TONE) != 0) {
                usb_send("TONE enabled=%d", s_tone_on ? 1 : 0);
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
