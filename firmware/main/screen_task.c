/*
 * screen_task.c owns LVGL. It is the only file in firmware/main that calls
 * LVGL or the board support package's display functions. The board support
 * package's LVGL port task runs LVGL's timers, and this task holds the port's
 * lock for every change. In this feature the screen shows a plain holding
 * screen with the words "Tremor log", the uptime, and the name of the face
 * state that the state task gives. Feature 11 draws the face.
 */

#include <stdint.h>
#include <stdio.h>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#include "bsp/esp-bsp.h"
#include "bsp/touch.h"
#include "esp_lcd_touch.h"
#include "esp_lvgl_port.h"
#include "face.h"
#include "lvgl.h"
#include "tasks.h"

static lv_obj_t *s_uptime_label;
static lv_obj_t *s_face_label;

/* on_click() runs in the LVGL port task, which holds the lock. It sends the
 * point of each tap. */
static void on_click(lv_event_t *e)
{
    (void)e;
    lv_point_t point = {0};
    lv_indev_t *indev = lv_indev_active();
    if (indev != NULL) {
        lv_indev_get_point(indev, &point);
    }
    usb_send("TOUCH x=%ld y=%ld", (long)point.x, (long)point.y);
}

static void build_screen(void)
{
    bsp_display_lock(0);
    lv_obj_t *scr = lv_screen_active();
    lv_obj_add_flag(scr, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(scr, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_event_cb(scr, on_click, LV_EVENT_CLICKED, NULL);

    lv_obj_t *title = lv_label_create(scr);
    lv_obj_set_style_text_font(title, &lv_font_montserrat_48, 0);
    lv_label_set_text(title, "Tremor log");
    lv_obj_align(title, LV_ALIGN_CENTER, 0, -50);

    s_uptime_label = lv_label_create(scr);
    lv_obj_set_style_text_font(s_uptime_label, &lv_font_montserrat_48, 0);
    lv_label_set_text(s_uptime_label, "0:00:00");
    lv_obj_align(s_uptime_label, LV_ALIGN_CENTER, 0, 30);

    s_face_label = lv_label_create(scr);
    lv_obj_set_style_text_font(s_face_label, &lv_font_montserrat_28, 0);
    lv_label_set_text(s_face_label, face_name(FACE_WAITING));
    lv_obj_align(s_face_label, LV_ALIGN_CENTER, 0, 100);
    bsp_display_unlock();
}

static void show_uptime(uint32_t uptime_s, face_state_t face)
{
    char text[24];
    snprintf(text, sizeof text, "%lu:%02lu:%02lu", (unsigned long)(uptime_s / 3600),
             (unsigned long)(uptime_s / 60 % 60), (unsigned long)(uptime_s % 60));
    bsp_display_lock(0);
    lv_label_set_text(s_uptime_label, text);
    lv_label_set_text(s_face_label, face_name(face));
    bsp_display_unlock();
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
 * start_display() does the work of bsp_display_start() with one change.
 * Waveshare's board support package 2.0.0 adds its SH8601 panel with
 * lvgl_port_add_disp_rgb(), which registers RGB panel callbacks on a panel
 * that is not an RGB panel. That writes past the panel's memory and broke the
 * heap on the watch. This function adds the panel with lvgl_port_add_disp()
 * and keeps every other setting of the board support package.
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

    esp_lcd_touch_handle_t touch = NULL;
    if (bsp_touch_new(NULL, &touch) != ESP_OK) {
        return NULL;
    }
    const lvgl_port_touch_cfg_t touch_cfg = {
        .disp = disp,
        .handle = touch,
    };
    if (lvgl_port_add_touch(&touch_cfg) == NULL) {
        return NULL;
    }
    if (bsp_display_brightness_set(100) != ESP_OK) {
        return NULL;
    }
    return disp;
}

static TickType_t ticks_until(int64_t due_us)
{
    int64_t wait_us = due_us - esp_timer_get_time();
    if (wait_us <= 0) {
        return 0;
    }
    return pdMS_TO_TICKS(wait_us / 1000) + 1;
}

void screen_task(void *arg)
{
    (void)arg;
    send_task_line("screen");

    if (start_display() == NULL) {
        usb_send("SCREEN_ERROR display did not start");
    } else {
        build_screen();
    }

    uint32_t updates = 0;
    uint32_t minute = 1;
    face_state_t face = FACE_WAITING;
    uint32_t face_changes = 0;
    for (;;) {
        int64_t due_us = (int64_t)minute * MINUTE_US;
        screen_msg_t msg;
        if (xQueueReceive(g_screen_queue, &msg, ticks_until(due_us)) == pdTRUE) {
            if ((face_state_t)msg.face != face) {
                face = (face_state_t)msg.face;
                face_changes++;
            }
            if (s_uptime_label != NULL) {
                show_uptime(msg.uptime_s, face);
                updates++;
            }
        }
        if (esp_timer_get_time() >= due_us) {
            usb_send("SCREEN_MINUTE minute=%lu updates=%lu face=%d face_changes=%lu", (unsigned long)minute,
                     (unsigned long)updates, (int)face, (unsigned long)face_changes);
            minute++;
        }
    }
}
