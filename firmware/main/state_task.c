/*
 * state_task.c owns the current state. It holds the face state, the session
 * share, the dose schedule, and the doses taken, and its rules live in
 * core/session.c.
 *
 * The task takes each new stretch and each answer from the pipeline task and
 * writes a GAP line, or an ANSWER line and the W line of the recording. When
 * the shown state changes, it writes a FACE line and the F line. It ticks the
 * doses once a second. It builds the view with view_build() from core/view.h
 * and sends it to the screen task once a second and after each change. It
 * never waits on the screen queue, and it counts each view it drops.
 *
 * A "Took it" tap comes from the screen task. The task gives it to
 * sess_took_it(), and when the tap is accepted it writes a DOSE line, the D
 * line of the recording, and the FACE and F lines when the shown state
 * changed. When the tap is refused it writes a DOSE_REFUSED line. The task
 * reads the power chip at start and every 10 seconds for the Status screen.
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

#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "power.h"
#include "record.h"
#include "session.h"
#include "settings.h"
#include "tasks.h"
#include "view.h"

#define SECOND_TICKS pdMS_TO_TICKS(1000)
#define POWER_EVERY_S 10

static sess_t s_sess;
static uint32_t s_screen_drops;
static bool s_tone_on;
static view_t s_view;
static view_input_t s_input;
/* The accepted and refused "Took it" taps since boot. */
static uint32_t s_took_it;
static uint32_t s_refused;
static power_info_t s_power;
static bool s_power_ok;

/* read_power() reads the power chip for the Status screen. */
static void read_power(void)
{
    power_info_t info = {0};
    s_power_ok = power_read(&info) == ESP_OK;
    s_power = info;
    s_input.battery_known = s_power_ok && info.battery_in && info.battery_percent >= 0;
    s_input.battery_mv = info.battery_mv;
    s_input.battery_percent = info.battery_percent;
}

/* send_screen() builds the view and sends it to the screen task with no
 * wait. */
static void send_screen(void)
{
    int64_t now_us = esp_timer_get_time();
    s_input.uptime_s = (uint32_t)(now_us / 1000000);
    s_input.recording = atomic_load(&g_recording_on);
    s_input.tone_on = s_tone_on;
    view_build(&s_view, &s_sess, &s_input, now_us);
    if (xQueueSend(g_screen_queue, &s_view, 0) != pdTRUE) {
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
    if (line_made(rec_face(line, sizeof line, now_us, shown)) > 0) {
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
    s_input.has_answer = true;
    s_input.stretch = m->stretch;
    s_input.rate_uhz = m->rate_uhz;
    if (m->has_window) {
        s_input.run_us = m->run_us;
    }
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
    if (line_made(rec_window(line, sizeof line, m->stretch, m->has_window, m->window, (res_code_t)m->code, m->prob,
            m->below, m->peak_hz)) > 0) {
        usb_send("%s", line);
    }
    after_call(flags);
}

/* take_took_it() takes a "Took it" tap from the screen task. */
static void take_took_it(const state_msg_t *m)
{
    unsigned flags = sess_took_it(&s_sess, m->at_us);
    if ((flags & SESS_DOSE_LOGGED) == 0) {
        s_refused++;
        usb_send("DOSE_REFUSED at_us=%lld", (long long)m->at_us);
        return;
    }
    s_took_it++;
    s_input.doses_accepted++;
    dose_entry_t dose;
    if (dose_last(&s_sess.dose, &dose)) {
        usb_send("DOSE at_us=%lld answers_local_us=%lld count=%lu", (long long)dose.time_us,
                 (long long)dose.answers_local_us, (unsigned long)dose_count(&s_sess.dose));
        char line[REC_LINE_MAX];
        if (line_made(rec_dose(line, sizeof line, &dose)) > 0) {
            usb_send("%s", line);
        }
    }
    after_call(flags);
    if ((flags & SESS_FACE_CHANGED) == 0) {
        send_screen();
    }
}

/* reply() sends the A line of a command. */
static void reply(rec_cmd_t command, rec_result_t result)
{
    char line[REC_LINE_MAX];
    if (line_made(rec_reply(line, sizeof line, command, result)) > 0) {
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

/* load_settings() loads the schedule and the tone setting at start. Each
 * setting that loaded is used, even when the other one was bad, because
 * settings_load() leaves a bad setting at its default. A schedule that
 * dose_set_schedule() refuses counts as a store error, and the schedule stays
 * off. */
static void load_settings(void)
{
    settings_t settings;
    settings_status_t status = settings_load(&settings);
    s_tone_on = settings.tone_on;
    if (!dose_set_schedule(&s_sess.dose, &settings.schedule, esp_timer_get_time())) {
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
        send_screen();
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
        send_screen();
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
        if (!changed) {
            send_screen();
        }
        break;
    }
    case REC_CMD_TONE: {
        s_tone_on = c->tone_on;
        bool stored = settings_save_tone(s_tone_on);
        send_settings("command", stored ? "ok" : "error");
        reply(REC_CMD_TONE, stored ? REC_DONE : REC_NOT_STORED);
        send_screen();
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
             "blocks=%lu screen_drops=%lu stack_free=%lu clock=%d schedule=%u due=%d doses=%lu tone=%d "
             "battery=%d battery_mv=%u battery_percent=%d took_it=%lu refused=%lu",
             (unsigned long)minute, (unsigned long)total, (unsigned long)a[RES_TREMOR],
             (unsigned long)a[RES_NO_TREMOR], (unsigned long)a[RES_ARM_MOVING], (unsigned long)a[RES_WARMING_UP],
             (unsigned long)a[RES_SENSOR_FAULT], (unsigned long)sh->tremor,
             (unsigned long)(sh->tremor + sh->no_tremor), (unsigned long)sh->moving, share,
             (int)face_shown(&s_sess.face), (unsigned long)s_sess.face_changes, (unsigned long)s_sess.gaps,
             (unsigned long)share_block_count(sh), (unsigned long)s_screen_drops,
             (unsigned long)uxTaskGetStackHighWaterMark(NULL), s_sess.dose.clock_set ? 1 : 0,
             (unsigned)s_sess.dose.schedule.count, dose_is_due(&s_sess.dose) ? 1 : 0,
             (unsigned long)dose_count(&s_sess.dose), s_tone_on ? 1 : 0, s_power.battery_in ? 1 : 0,
             (unsigned)s_power.battery_mv, s_power.battery_percent, (unsigned long)s_took_it,
             (unsigned long)s_refused);
}

void state_task(void *arg)
{
    (void)arg;
    send_task_line("state");
    sess_init(&s_sess, esp_timer_get_time());
    load_settings();
    s_input.firmware = FIRMWARE_VERSION;
    s_input.hash = TABLE_HASH;
    read_power();
    send_screen();

    /* The task waits at most 1 second for a message, and a settings store
     * write takes well under a second, so the watchdog's 5 seconds run out
     * only when the task is stuck. */
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    TickType_t next_second = xTaskGetTickCount() + SECOND_TICKS;
    uint32_t minute = 1;
    uint32_t seconds = 0;
    state_msg_t msg;
    for (;;) {
        esp_task_wdt_reset();
        TickType_t now = xTaskGetTickCount();
        TickType_t wait = (TickType_t)(next_second - now) <= SECOND_TICKS ? next_second - now : 0;
        if (xQueueReceive(g_state_queue, &msg, wait) == pdTRUE) {
            if (msg.kind == STATE_MSG_STRETCH) {
                take_stretch(&msg);
            } else if (msg.kind == STATE_MSG_COMMAND) {
                take_command(&msg);
            } else if (msg.kind == STATE_MSG_TOOK_IT) {
                take_took_it(&msg);
            } else {
                take_answer(&msg);
            }
        }
        if ((TickType_t)(xTaskGetTickCount() - next_second) < (TickType_t)0x80000000u) {
            next_second += SECOND_TICKS;
            unsigned flags = sess_tick(&s_sess, esp_timer_get_time());
            if ((flags & SESS_TONE) != 0) {
                s_input.dose_tones++;
                usb_send("TONE enabled=%d", s_tone_on ? 1 : 0);
            }
            if (++seconds % POWER_EVERY_S == 0) {
                read_power();
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
