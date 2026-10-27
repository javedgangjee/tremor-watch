/*
 * screen_task.c owns LVGL and the audio codec. It and face_draw.c are the
 * only files in firmware/main that call LVGL or the board support package's
 * display functions. The board support package's LVGL port task runs LVGL's
 * timers, and this task holds the port's lock for every LVGL call and every
 * call of core/screens.h.
 *
 * The task starts the display, the touch, the codec, and the BOOT button,
 * builds the face, and writes the SCREEN_START line. Then it runs a round
 * every 20 milliseconds. Each round reads the BOOT button, ends the Logged
 * view and the screens left unused, takes the newest view from the state
 * task, plays the dose tone and shows the Logged view when the view's counts
 * rise, feeds the tone, and writes the SCREEN_VIEW, TONE_PLAY, BUTTON, and
 * SCREEN_MINUTE lines.
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "driver/gpio.h"
#include "esp_attr.h"
#include "esp_heap_caps.h"
#include "esp_private/cache_utils.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "bsp/esp-bsp.h"
#include "bsp/touch.h"
#include "esp_lcd_touch.h"
#include "esp_lvgl_port.h"
#include "face_draw.h"
#include "lvgl.h"
#include "screens.h"
#include "tasks.h"
#include "tone_out.h"
#include "view.h"

/* The BOOT button is GPIO0 with the chip's pull-up, and it reads low while it
 * is pressed. */
#define BOOT_GPIO GPIO_NUM_0
#define ROUND_MS 20
/* malloc() puts every block of this many bytes or more in PSRAM, so LVGL's
 * small allocations stay out of internal memory. The display driver needs a
 * block of about 82 KB of internal memory for each transfer, and LVGL objects
 * there would break that block up. */
#define EXTERNAL_FROM_BYTES 0

static scr_t s_scr;
static view_t s_view;
static bool s_have_view;
static bool s_face_ok;
/* The counts of dose tones and accepted doses in the last view. */
static uint32_t s_dose_tones;
static uint32_t s_doses_accepted;
static uint32_t s_took_it_drops;

/* The fields of the last SCREEN_VIEW line. */
typedef struct {
    look_screen_t screen;
    face_state_t face;
    char time[8];
    bool due;
    char next[8];
    char last_tremor[8];
    int share;
    uint32_t blocks;
    char hollow[SHARE_BLOCKS + 1];
} view_line_t;

static view_line_t s_line;
static bool s_line_sent;

/* The touch handle and the LVGL port's touch handler. s_touch_waiting is true
 * when a touch interrupt came while the flash cache was off. */
static esp_lcd_touch_handle_t s_touch;
static esp_lcd_touch_interrupt_callback_t s_touch_wake;
static volatile bool s_touch_waiting;

void screen_took_it(int64_t at_us)
{
    state_msg_t msg = {.kind = STATE_MSG_TOOK_IT, .at_us = at_us};
    if (xQueueSend(g_state_queue, &msg, 0) != pdTRUE) {
        s_took_it_drops++;
    }
}

/* rounder() widens each area to even starts and odd ends, because the
 * SH8601 panel takes whole pairs of pixels. It is the same rule as the board
 * support package's own rounder. */
static void rounder(lv_event_t *e)
{
    lv_area_t *area = (lv_area_t *)lv_event_get_param(e);
    area->x1 = (area->x1 >> 1) << 1;
    area->y1 = (area->y1 >> 1) << 1;
    area->x2 = ((area->x2 >> 1) << 1) + 1;
    area->y2 = ((area->y2 >> 1) << 1) + 1;
}

/*
 * start_display() does the display part of the board support package's own
 * display start function with one change. Waveshare's board support package
 * 2.0.0 adds its SH8601 panel with lvgl_port_add_disp_rgb(), which registers
 * RGB panel callbacks on a panel that is not an RGB panel. That writes past
 * the panel's memory and corrupts the heap. This function adds the panel with
 * lvgl_port_add_disp() and keeps every other setting of the board support
 * package.
 */
static lv_display_t *start_display(void)
{
    const lvgl_port_cfg_t port_cfg = ESP_LVGL_PORT_INIT_CONFIG();
    if (lvgl_port_init(&port_cfg) != ESP_OK) {
        return NULL;
    }
    const bsp_display_config_t panel_cfg = {
        .max_transfer_sz = BSP_LCD_H_RES * BSP_LCD_V_RES * BSP_LCD_BITS_PER_PIXEL / 8,
    };
    esp_lcd_panel_handle_t panel = NULL;
    esp_lcd_panel_io_handle_t io = NULL;
    if (bsp_display_new(&panel_cfg, &panel, &io) != ESP_OK) {
        return NULL;
    }
    const lvgl_port_display_cfg_t disp_cfg = {
        .io_handle = io,
        .panel_handle = panel,
        .buffer_size = BSP_LCD_H_RES * LVGL_BUFFER_HEIGHT,
        .monochrome = false,
        .hres = BSP_LCD_H_RES,
        .vres = BSP_LCD_V_RES,
        .color_format = LV_COLOR_FORMAT_RGB565,
        .flags = {
            .sw_rotate = true,
            .buff_dma = false,
            .swap_bytes = true,
        },
    };
    lv_display_t *disp = lvgl_port_add_disp(&disp_cfg);
    if (disp == NULL) {
        return NULL;
    }
    lvgl_port_lock(0);
    lv_display_add_event_cb(disp, rounder, LV_EVENT_INVALIDATE_AREA, NULL);
    lvgl_port_unlock();
    if (bsp_display_brightness_set(100) != ESP_OK) {
        return NULL;
    }
    return disp;
}

/*
 * on_touch() takes the touch pin's interrupt in place of the LVGL port's own
 * handler. main.c puts the GPIO interrupt in IRAM, so the sensor's INT1 stamps
 * stay on time while the settings store writes to flash with the cache off.
 * The port's handler calls code in flash and reads the touch handle in PSRAM,
 * and the cache serves both. So on_touch() calls the port's handler only while
 * the cache is on. Otherwise it leaves the touch for the next round of the
 * screen task. Every settings store call comes from the state task on core 0,
 * which is the core of the GPIO interrupt, so the cache cannot turn off while
 * on_touch() runs.
 */
static void IRAM_ATTR on_touch(void *arg)
{
    (void)arg;
    if (spi_flash_cache_enabled()) {
        s_touch_wake(s_touch);
    } else {
        s_touch_waiting = true;
    }
}

static bool start_touch(lv_display_t *disp)
{
    esp_lcd_touch_handle_t touch = NULL;
    if (bsp_touch_new(NULL, &touch) != ESP_OK) {
        return false;
    }
    const lvgl_port_touch_cfg_t touch_cfg = {
        .disp = disp,
        .handle = touch,
    };
    if (lvgl_port_add_touch(&touch_cfg) == NULL) {
        return false;
    }
    s_touch = touch;
    s_touch_wake = touch->config.interrupt_callback;
    return s_touch_wake != NULL && gpio_isr_handler_add(BSP_LCD_TOUCH_INT, on_touch, NULL) == ESP_OK;
}

static bool start_button(void)
{
    const gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << BOOT_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    return gpio_config(&cfg) == ESP_OK;
}

static const char *screen_name(look_screen_t screen)
{
    switch (screen) {
    case LOOK_HOME:
        return "home";
    case LOOK_MEDICATION:
        return "medication";
    case LOOK_LOGGED:
        return "logged";
    case LOOK_SESSION:
        return "session";
    default:
        return "status";
    }
}

/* send_view_line() writes the SCREEN_VIEW line when one of its fields
 * changed. It returns true when it wrote one. */
static bool send_view_line(look_screen_t shown)
{
    if (!s_have_view) {
        return false;
    }
    view_line_t now;
    memset(&now, 0, sizeof now);
    now.screen = shown;
    now.face = s_view.face;
    snprintf(now.time, sizeof now.time, "%s", s_view.time);
    now.due = s_view.due;
    snprintf(now.next, sizeof now.next, "%s", s_view.next_short);
    snprintf(now.last_tremor, sizeof now.last_tremor, "%s", s_view.last_tremor_short);
    now.share = s_view.percent;
    now.blocks = s_view.block_count;
    for (uint32_t i = 0; i < s_view.block_count && i < SHARE_BLOCKS; i++) {
        now.hollow[i] = s_view.hollow[i] ? '1' : '0';
    }
    if (s_line_sent && memcmp(&now, &s_line, sizeof now) == 0) {
        return false;
    }
    s_line = now;
    s_line_sent = true;
    const look_state_t *l = look_state(now.face);
    usb_send("SCREEN_VIEW at_us=%lld screen=%s face=%d circle=%s colour=%06lx time=%s due=%d next=%s "
             "last_tremor=%s share=%d blocks=%lu hollow=%s",
             (long long)esp_timer_get_time(), screen_name(now.screen), (int)now.face,
             l->filled ? "fill" : "outline", (unsigned long)l->circle, now.time, now.due ? 1 : 0, now.next,
             now.last_tremor, now.share, (unsigned long)now.blocks, now.blocks > 0 ? now.hollow : "none");
    return true;
}

/* take_views() takes every view in the queue and keeps the newest. It
 * returns true when it took one. */
static bool take_views(void)
{
    bool got = false;
    while (xQueueReceive(g_screen_queue, &s_view, 0) == pdTRUE) {
        got = true;
    }
    return got;
}



void screen_task(void *arg)
{
    (void)arg;
    send_task_line("screen");

    heap_caps_malloc_extmem_enable(EXTERNAL_FROM_BYTES);
    lv_display_t *disp = start_display();
    bool touch_ok = disp != NULL && start_touch(disp);
    bool audio_ok = tone_out_init();
    bool button_ok = start_button();
    scr_init(&s_scr, esp_timer_get_time());
    if (disp != NULL) {
        bsp_display_lock(0);
        s_face_ok = face_draw_init(&s_scr);
        bsp_display_unlock();
    }
    usb_send("SCREEN_START at_us=%lld display=%s touch=%s audio=%s button=%s face=%s internal_free=%u "
             "internal_largest=%u",
             (long long)esp_timer_get_time(), disp != NULL ? "ok" : "error", touch_ok ? "ok" : "error",
             audio_ok ? "ok" : "error", button_ok ? "ok" : "error", s_face_ok ? "ok" : "error",
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
             (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL));
    if (disp == NULL) {
        usb_send("SCREEN_ERROR display did not start");
    } else if (!s_face_ok) {
        usb_send("SCREEN_ERROR face did not build");
    }

    uint32_t updates = 0;
    uint32_t views = 0;
    uint32_t tones = 0;
    uint32_t face_changes = 0;
    face_state_t face = FACE_WAITING;
    uint32_t minute = 1;
    /* A round takes about ROUND_MS and waits on the display lock, so the
     * watchdog's 5 seconds run out only when the task or LVGL is stuck. */
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    TickType_t last_wake = xTaskGetTickCount();
    for (;;) {
        esp_task_wdt_reset();
        if (s_touch_waiting) {
            s_touch_waiting = false;
            s_touch_wake(s_touch);
        }
        int64_t now_us = esp_timer_get_time();
        bool down = button_ok && gpio_get_level(BOOT_GPIO) == 0;
        bool got = take_views();
        int dose_tone = 0;
        unsigned button = 0;
        bsp_display_lock(0);
        button = scr_button(&s_scr, down, now_us);
        scr_tick(&s_scr, now_us);
        if (got) {
            updates++;
            if (s_have_view && s_view.doses_accepted != s_doses_accepted) {
                scr_logged(&s_scr, now_us);
            }
            if (s_have_view && s_view.dose_tones != s_dose_tones && s_view.tone_on) {
                dose_tone = 1;
            }
            s_doses_accepted = s_view.doses_accepted;
            s_dose_tones = s_view.dose_tones;
            s_have_view = true;
            if (s_face_ok) {
                face_draw_view(&s_view);
            }
            if (s_view.face != face) {
                face = s_view.face;
                face_changes++;
            }
        }
        if (s_face_ok) {
            face_draw_show(scr_screen(&s_scr), now_us);
        }
        look_screen_t screen = scr_screen(&s_scr);
        look_screen_t shown = s_face_ok ? face_draw_shown() : screen;
        uint32_t taps = s_face_ok ? face_draw_taps() : 0;
        uint32_t mismatches = s_face_ok ? face_draw_mismatches() : 0;
        bsp_display_unlock();

        if ((button & SCR_CHANGED) != 0) {
            usb_send("BUTTON at_us=%lld screen=%s", (long long)now_us, screen_name(screen));
        }
        if (dose_tone) {
            tone_out_start(TONE_DOSE);
        }
        int started = tone_out_feed();
        if (started >= 0) {
            tones++;
            usb_send("TONE_PLAY at_us=%lld kind=%s tones=%d", (long long)esp_timer_get_time(),
                     started == TONE_DOSE ? "dose" : "tap", started == TONE_DOSE ? 3 : 1);
        }
        /* A newer view waits when the state task ran during this round. Its
         * SCREEN_VIEW line comes next round, so a line never shows an older
         * view after a line that the state task wrote for the newer one. The
         * state task cannot run between the test and the line, because the
         * scheduler is paused on this core, which tasks.h makes the state
         * task's core too, and usb_send() does not wait. */
        vTaskSuspendAll();
        if (uxQueueMessagesWaiting(g_screen_queue) == 0 && send_view_line(shown)) {
            views++;
        }
        xTaskResumeAll();
        if (esp_timer_get_time() >= (int64_t)minute * MINUTE_US) {
            usb_send("SCREEN_MINUTE minute=%lu updates=%lu face=%d face_changes=%lu views=%lu taps=%lu tones=%lu "
                     "stack_free=%lu internal_min=%u width_mismatch=%lu took_it_drops=%lu",
                     (unsigned long)minute, (unsigned long)updates, (int)face, (unsigned long)face_changes,
                     (unsigned long)views, (unsigned long)taps, (unsigned long)tones,
                     (unsigned long)uxTaskGetStackHighWaterMark(NULL),
                     (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL), (unsigned long)mismatches,
                     (unsigned long)s_took_it_drops);
            minute++;
        }
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(ROUND_MS));
    }
}
