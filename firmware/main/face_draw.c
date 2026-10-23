/*
 * face_draw.c builds and changes the LVGL objects of the face. face_draw.h
 * describes it, and feature 11's requirements 42 to 58 give the details.
 *
 * Each screen is one full-screen object, and every other object of the screen
 * is its direct child, placed at its box from core/look.h. Children take no
 * clicks, so a tap anywhere reaches the screen's click event. No object uses
 * a transform. The pulse, the press, and the Logged view's pop change the
 * size of a plain object around its centre, and the tick is uncovered by an
 * object that clips it.
 */

#include "face_draw.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "esp_timer.h"

#include "face_icons.h"
#include "lvgl.h"
#include "tasks.h"
#include "tone_out.h"

LV_FONT_DECLARE(face_font_28)
LV_FONT_DECLARE(face_font_40)
LV_FONT_DECLARE(face_font_56)
LV_FONT_DECLARE(face_font_96)

/* The pulse lasts 2.4 seconds, grows to 120 percent, starts at 45 percent
 * opacity, and is 6 pixels wide. */
#define PULSE_MS 2400
#define PULSE_GROW_PCT 20
#define PULSE_OPA 115
#define PULSE_WIDTH 6
/* The press shrinks a card to 95 percent for 150 milliseconds and back. */
#define PRESS_MS 150
#define PRESS_PCT 95
#define PRESS_US (2 * PRESS_MS * 1000)
/* The Logged circle grows from 90 to 103 to 100 percent over about 1 second,
 * and the tick is uncovered over about 1.3 seconds. */
#define POP_UP_MS 560
#define POP_DOWN_MS 480
#define POP_FROM 900
#define POP_TOP 1030
#define POP_END 1000
#define TICK_MS 1280
/* The battery's border and nub. */
#define BATTERY_BORDER 3
#define BATTERY_NUB_W 5
#define BATTERY_NUB_H 12
/* The blocks have gaps of 4 pixels, a hollow block has a border of 3 pixels,
 * and a bar is at least 4 pixels tall. */
#define BLOCK_GAP 4
#define BLOCK_BORDER 3
#define BAR_MIN 4

typedef struct {
    lv_obj_t *root;
    lv_obj_t *card;
    /* Home and Logged. */
    lv_obj_t *time;
    lv_obj_t *date;
    lv_obj_t *battery;
    lv_obj_t *line;
    lv_obj_t *pulse;
    lv_obj_t *circle;
    lv_obj_t *icon;
    lv_obj_t *word;
    /* Logged. */
    lv_obj_t *tick_clip;
    /* Medication. */
    lv_obj_t *label_1;
    lv_obj_t *value_1;
    lv_obj_t *label_2;
    lv_obj_t *value_2;
    lv_obj_t *button;
    /* Session. */
    lv_obj_t *share;
    lv_obj_t *share_line;
    lv_obj_t *blocks_left;
    lv_obj_t *blocks_right;
    lv_obj_t *columns[SHARE_BLOCKS];
    lv_obj_t *bars[SHARE_BLOCKS];
    /* Status. */
    lv_obj_t *status_label[LOOK_STATUS_ROWS];
    lv_obj_t *status_value[LOOK_STATUS_ROWS];
} screen_objs_t;

static const lv_image_dsc_t *const ICONS[LOOK_ICON_COUNT] = {
    [LOOK_ICON_TREMOR] = &face_icon_tremor,
    [LOOK_ICON_NO_TREMOR] = &face_icon_no_tremor,
    [LOOK_ICON_ARM_MOVING] = &face_icon_arm_moving,
    [LOOK_ICON_WAITING] = &face_icon_waiting,
    [LOOK_ICON_DOSE_DUE] = &face_icon_dose_due,
    [LOOK_ICON_CHECK] = &face_icon_check,
    [LOOK_ICON_LOGGED_RING] = &face_icon_logged_ring,
    [LOOK_ICON_LOGGED_TICK] = &face_icon_logged_tick,
};

static screen_objs_t s_objs[LOOK_SCREEN_COUNT];
static scr_t *s_scr;
static look_screen_t s_shown = LOOK_HOME;
static bool s_have_face;
static face_state_t s_face;
static bool s_tone_on;
static int64_t s_hold_until_us;
static uint32_t s_taps;
static uint32_t s_mismatches;
static bool s_ok;

static lv_color_t colour(uint32_t rgb)
{
    return lv_color_hex(rgb);
}

static const lv_font_t *font_of(int size)
{
    switch (size) {
    case 40:
        return &face_font_40;
    case 56:
        return &face_font_56;
    case 96:
        return &face_font_96;
    default:
        return &face_font_28;
    }
}

/* check() notes an object that could not be made. */
static lv_obj_t *check(lv_obj_t *obj)
{
    if (obj == NULL) {
        s_ok = false;
    }
    return obj;
}

/* plain() makes a plain object with no theme style that takes no clicks. */
static lv_obj_t *plain(lv_obj_t *parent, int x, int y, int w, int h)
{
    lv_obj_t *obj = check(lv_obj_create(parent));
    if (obj == NULL) {
        return NULL;
    }
    lv_obj_remove_style_all(obj);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_pos(obj, x, y);
    lv_obj_set_size(obj, w, h);
    return obj;
}

static lv_obj_t *filled(lv_obj_t *parent, int x, int y, int w, int h, uint32_t rgb, int radius)
{
    lv_obj_t *obj = plain(parent, x, y, w, h);
    if (obj != NULL) {
        lv_obj_set_style_bg_color(obj, colour(rgb), 0);
        lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(obj, radius, 0);
    }
    return obj;
}

static lv_obj_t *label_at(lv_obj_t *parent, int x, int y, int w, int h, int size, look_align_t align, uint32_t rgb)
{
    lv_obj_t *obj = check(lv_label_create(parent));
    if (obj == NULL) {
        return NULL;
    }
    lv_obj_remove_style_all(obj);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_pos(obj, x, y);
    lv_obj_set_size(obj, w, h);
    lv_label_set_long_mode(obj, LV_LABEL_LONG_MODE_CLIP);
    lv_obj_set_style_text_font(obj, font_of(size), 0);
    lv_obj_set_style_text_color(obj, colour(rgb), 0);
    lv_obj_set_style_text_align(obj,
                                align == LOOK_ALIGN_CENTER  ? LV_TEXT_ALIGN_CENTER
                                : align == LOOK_ALIGN_RIGHT ? LV_TEXT_ALIGN_RIGHT
                                                            : LV_TEXT_ALIGN_LEFT,
                                0);
    lv_label_set_text(obj, "");
    return obj;
}

static lv_obj_t *label_box(lv_obj_t *parent, look_screen_t screen, look_item_t item)
{
    const look_box_t *b = look_box(screen, item);
    return label_at(parent, b->x, b->y, b->w, b->h, b->size, b->align, b->colour);
}

static lv_obj_t *icon_at(lv_obj_t *parent, int x, int y, look_icon_t icon, uint32_t rgb)
{
    lv_obj_t *obj = check(lv_image_create(parent));
    if (obj == NULL) {
        return NULL;
    }
    lv_obj_remove_style_all(obj);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_CLICKABLE);
    lv_image_set_src(obj, ICONS[icon]);
    lv_obj_set_pos(obj, x, y);
    lv_obj_set_size(obj, LOOK_ICON_PX, LOOK_ICON_PX);
    lv_obj_set_style_image_recolor(obj, colour(rgb), 0);
    lv_obj_set_style_image_recolor_opa(obj, LV_OPA_COVER, 0);
    return obj;
}

/* set_text() sets a label's text at the size that fits its box, cuts a text
 * that is still too wide, and counts a width that differs from core/look.h. */
static void set_text(lv_obj_t *label, look_screen_t screen, look_item_t item, const char *text, const view_cut_t *cut)
{
    if (label == NULL) {
        return;
    }
    const look_box_t *b = look_box(screen, item);
    char out[VIEW_TEXT_MAX + 4];
    int size = look_fit_size(text, b->w, b->size, b->smallest);
    if (size == 0) {
        size = b->smallest;
        if (cut == NULL || look_cut(text, cut->cut_at, cut->cut_len, b->w, size, out, sizeof out) == 0) {
            snprintf(out, sizeof out, "%s", text);
        }
        text = out;
    }
    const lv_font_t *font = font_of(size);
    if (strcmp(lv_label_get_text(label), text) == 0 && lv_obj_get_style_text_font(label, 0) == font) {
        return;
    }
    lv_obj_set_style_text_font(label, font, 0);
    lv_label_set_text(label, text);
    lv_point_t got;
    lv_text_get_size(&got, text, font, 0, 0, LV_COORD_MAX, LV_TEXT_FLAG_NONE);
    if (got.x != look_text_width(text, size)) {
        s_mismatches++;
    }
}

static void set_text_colour(lv_obj_t *label, uint32_t rgb)
{
    if (label != NULL) {
        lv_obj_set_style_text_color(label, colour(rgb), 0);
    }
}

/* ------------------------------------------------------------ animations */

static void anim_size_cb(void *var, int32_t v)
{
    lv_obj_t *obj = var;
    const lv_area_t *home = lv_obj_get_user_data(obj);
    if (home == NULL) {
        return;
    }
    int32_t w0 = lv_area_get_width(home);
    int32_t h0 = lv_area_get_height(home);
    int32_t w = w0 * v / 1000;
    int32_t h = h0 * v / 1000;
    lv_obj_set_pos(obj, home->x1 + (w0 - w) / 2, home->y1 + (h0 - h) / 2);
    lv_obj_set_size(obj, w, h);
}

/* anim_pop_cb() takes the time in milliseconds from the start of the pop and
 * sets the circle's size, which grows from 90 to 103 percent and settles at
 * 100 percent. LVGL keeps only one animation for an object and a callback, so
 * one animation gives both parts. */
static void anim_pop_cb(void *var, int32_t ms)
{
    int32_t scale = ms < POP_UP_MS ? POP_FROM + (POP_TOP - POP_FROM) * ms / POP_UP_MS
                                   : POP_TOP - (POP_TOP - POP_END) * (ms - POP_UP_MS) / POP_DOWN_MS;
    anim_size_cb(var, scale);
}

static void anim_opa_cb(void *var, int32_t v)
{
    lv_obj_set_style_border_opa(var, (lv_opa_t)v, 0);
}

static void anim_width_cb(void *var, int32_t v)
{
    lv_obj_set_width(var, v);
}

/* The home areas of the objects that change size. */
static lv_area_t s_home_area[LOOK_SCREEN_COUNT][3];

static void keep_home(lv_obj_t *obj, lv_area_t *area, int x, int y, int w, int h)
{
    if (obj == NULL) {
        return;
    }
    area->x1 = x;
    area->y1 = y;
    area->x2 = x + w - 1;
    area->y2 = y + h - 1;
    lv_obj_set_user_data(obj, area);
}

/* scale_anim() changes an object's size around its centre from `from` to
 * `to` in thousandths. */
static void scale_anim(lv_obj_t *obj, int32_t from, int32_t to, uint32_t ms, uint32_t delay_ms, uint32_t back_ms)
{
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, obj);
    lv_anim_set_exec_cb(&a, anim_size_cb);
    lv_anim_set_values(&a, from, to);
    lv_anim_set_duration(&a, ms);
    lv_anim_set_delay(&a, delay_ms);
    if (back_ms > 0) {
        lv_anim_set_reverse_duration(&a, back_ms);
    }
    lv_anim_set_path_cb(&a, lv_anim_path_ease_out);
    lv_anim_start(&a);
}

static void start_pulse(lv_obj_t *pulse, uint32_t rgb)
{
    if (pulse == NULL) {
        return;
    }
    lv_anim_delete(pulse, NULL);
    lv_obj_set_style_border_color(pulse, colour(rgb), 0);
    lv_obj_set_style_border_opa(pulse, PULSE_OPA, 0);
    lv_obj_remove_flag(pulse, LV_OBJ_FLAG_HIDDEN);
    scale_anim(pulse, 1000, 1000 + PULSE_GROW_PCT * 10, PULSE_MS, 0, 0);
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, pulse);
    lv_anim_set_exec_cb(&a, anim_opa_cb);
    lv_anim_set_values(&a, PULSE_OPA, 0);
    lv_anim_set_duration(&a, PULSE_MS);
    lv_anim_set_path_cb(&a, lv_anim_path_ease_out);
    lv_anim_start(&a);
}

static void press(lv_obj_t *card)
{
    if (card == NULL) {
        return;
    }
    lv_anim_delete(card, NULL);
    scale_anim(card, 1000, PRESS_PCT * 10, PRESS_MS, 0, PRESS_MS);
}

static void start_logged(void)
{
    screen_objs_t *o = &s_objs[LOOK_LOGGED];
    if (o->circle == NULL || o->tick_clip == NULL) {
        return;
    }
    lv_anim_delete(o->circle, NULL);
    lv_anim_delete(o->tick_clip, NULL);
    anim_size_cb(o->circle, POP_FROM);
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, o->circle);
    lv_anim_set_exec_cb(&a, anim_pop_cb);
    lv_anim_set_values(&a, 0, POP_UP_MS + POP_DOWN_MS);
    lv_anim_set_duration(&a, POP_UP_MS + POP_DOWN_MS);
    lv_anim_set_path_cb(&a, lv_anim_path_linear);
    lv_anim_start(&a);
    lv_obj_set_width(o->tick_clip, 0);
    lv_anim_init(&a);
    lv_anim_set_var(&a, o->tick_clip);
    lv_anim_set_exec_cb(&a, anim_width_cb);
    lv_anim_set_values(&a, 0, LOOK_ICON_PX);
    lv_anim_set_duration(&a, TICK_MS);
    lv_anim_set_path_cb(&a, lv_anim_path_ease_out);
    lv_anim_start(&a);
}

/* ---------------------------------------------------------------- build */

static void on_click(lv_event_t *e);

static void style_circle(screen_objs_t *o, const look_state_t *l)
{
    if (o->circle == NULL) {
        return;
    }
    if (l->filled) {
        lv_obj_set_style_bg_color(o->circle, colour(l->circle), 0);
        lv_obj_set_style_border_width(o->circle, 0, 0);
    } else {
        lv_obj_set_style_bg_color(o->circle, colour(LOOK_CARD), 0);
        lv_obj_set_style_border_color(o->circle, colour(l->circle), 0);
        lv_obj_set_style_border_width(o->circle, LOOK_OUTLINE, 0);
    }
    if (o->icon != NULL) {
        lv_image_set_src(o->icon, ICONS[l->icon]);
        lv_obj_set_style_image_recolor(o->icon, colour(l->ink), 0);
    }
    if (o->word != NULL) {
        lv_obj_set_style_text_color(o->word, colour(l->ink), 0);
        lv_label_set_text(o->word, l->word);
    }
}

static void build_root(look_screen_t screen)
{
    screen_objs_t *o = &s_objs[screen];
    o->root = filled(lv_screen_active(), 0, 0, LOOK_W, LOOK_H, LOOK_BG, 0);
    if (o->root == NULL) {
        return;
    }
    lv_obj_add_flag(o->root, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(o->root, on_click, LV_EVENT_CLICKED, (void *)(intptr_t)screen);
    const look_box_t *card = look_box(screen, LOOK_ITEM_CARD);
    o->card = filled(o->root, card->x, card->y, card->w, card->h, LOOK_CARD, LOOK_CARD_RADIUS);
    keep_home(o->card, &s_home_area[screen][0], card->x, card->y, card->w, card->h);
}

static void build_home(look_screen_t screen)
{
    screen_objs_t *o = &s_objs[screen];
    const look_box_t *bat = look_box(screen, LOOK_ITEM_BATTERY);
    const look_box_t *c = look_box(screen, LOOK_ITEM_CIRCLE);
    const look_box_t *icon = look_box(screen, LOOK_ITEM_CIRCLE_ICON);
    o->time = label_box(o->root, screen, LOOK_ITEM_TIME);
    o->date = label_box(o->root, screen, LOOK_ITEM_DATE);

    int body_w = bat->w - BATTERY_NUB_W - 1;
    lv_obj_t *body = plain(o->root, bat->x, bat->y, body_w, bat->h);
    if (body != NULL) {
        lv_obj_set_style_border_color(body, colour(LOOK_TEXT), 0);
        lv_obj_set_style_border_width(body, BATTERY_BORDER, 0);
        lv_obj_set_style_border_opa(body, LV_OPA_COVER, 0);
    }
    filled(o->root, bat->x + body_w + 1, bat->y + (bat->h - BATTERY_NUB_H) / 2, BATTERY_NUB_W, BATTERY_NUB_H,
           LOOK_TEXT, 0);
    int line_h = look_line_height(28);
    o->battery = label_at(o->root, bat->x, bat->y + (bat->h - line_h) / 2, body_w, line_h, 28, LOOK_ALIGN_CENTER,
                          LOOK_TEXT);

    o->pulse = plain(o->root, c->x, c->y, c->w, c->h);
    if (o->pulse != NULL) {
        lv_obj_set_style_radius(o->pulse, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_border_width(o->pulse, PULSE_WIDTH, 0);
        lv_obj_add_flag(o->pulse, LV_OBJ_FLAG_HIDDEN);
        keep_home(o->pulse, &s_home_area[screen][1], c->x, c->y, c->w, c->h);
    }
    o->circle = filled(o->root, c->x, c->y, c->w, c->h, LOOK_CARD, LV_RADIUS_CIRCLE);
    keep_home(o->circle, &s_home_area[screen][2], c->x, c->y, c->w, c->h);
    if (o->circle != NULL) {
        lv_obj_set_style_border_opa(o->circle, LV_OPA_COVER, 0);
    }
    const look_state_t *l = screen == LOOK_LOGGED ? look_logged() : look_state(FACE_WAITING);
    o->icon = icon_at(o->root, icon->x, icon->y, l->icon, l->ink);
    if (screen == LOOK_LOGGED) {
        o->tick_clip = plain(o->root, icon->x, icon->y, LOOK_ICON_PX, LOOK_ICON_PX);
        if (o->tick_clip != NULL) {
            icon_at(o->tick_clip, 0, 0, LOOK_ICON_LOGGED_TICK, l->ink);
        }
    }
    o->word = label_box(o->root, screen, LOOK_ITEM_CIRCLE_WORD);
    style_circle(o, l);
    o->line = label_box(o->root, screen, LOOK_ITEM_LINE);
}

static void build_medication(void)
{
    screen_objs_t *o = &s_objs[LOOK_MEDICATION];
    o->label_1 = label_box(o->root, LOOK_MEDICATION, LOOK_ITEM_DOSE_LABEL_1);
    o->value_1 = label_box(o->root, LOOK_MEDICATION, LOOK_ITEM_DOSE_VALUE_1);
    o->label_2 = label_box(o->root, LOOK_MEDICATION, LOOK_ITEM_DOSE_LABEL_2);
    o->value_2 = label_box(o->root, LOOK_MEDICATION, LOOK_ITEM_DOSE_VALUE_2);
    const look_box_t *b = look_box(LOOK_MEDICATION, LOOK_ITEM_BUTTON);
    o->button = filled(o->root, b->x, b->y, b->w, b->h, b->colour, 0);
    keep_home(o->button, &s_home_area[LOOK_MEDICATION][1], b->x, b->y, b->w, b->h);
    const look_box_t *icon = look_box(LOOK_MEDICATION, LOOK_ITEM_BUTTON_ICON);
    icon_at(o->root, icon->x, icon->y, LOOK_ICON_CHECK, icon->colour);
    lv_obj_t *word = label_box(o->root, LOOK_MEDICATION, LOOK_ITEM_BUTTON_WORD);
    set_text(word, LOOK_MEDICATION, LOOK_ITEM_BUTTON_WORD, "Took it", NULL);
}

static void build_session(void)
{
    screen_objs_t *o = &s_objs[LOOK_SESSION];
    o->share = label_box(o->root, LOOK_SESSION, LOOK_ITEM_SHARE);
    o->share_line = label_box(o->root, LOOK_SESSION, LOOK_ITEM_SHARE_LINE);
    o->blocks_left = label_box(o->root, LOOK_SESSION, LOOK_ITEM_BLOCKS_LEFT);
    o->blocks_right = label_box(o->root, LOOK_SESSION, LOOK_ITEM_BLOCKS_RIGHT);
    const look_box_t *area = look_box(LOOK_SESSION, LOOK_ITEM_BLOCKS);
    int col_w = (area->w - (SHARE_BLOCKS - 1) * BLOCK_GAP) / SHARE_BLOCKS;
    for (int i = 0; i < SHARE_BLOCKS; i++) {
        int x = area->x + i * (col_w + BLOCK_GAP);
        o->columns[i] = plain(o->root, x, area->y, col_w, area->h);
        if (o->columns[i] != NULL) {
            lv_obj_set_style_border_color(o->columns[i], colour(area->colour), 0);
            lv_obj_set_style_border_width(o->columns[i], BLOCK_BORDER, 0);
            lv_obj_set_style_border_opa(o->columns[i], LV_OPA_COVER, 0);
            lv_obj_add_flag(o->columns[i], LV_OBJ_FLAG_HIDDEN);
        }
        o->bars[i] = filled(o->root, x, area->y + area->h - BAR_MIN, col_w, BAR_MIN, area->colour, 0);
        if (o->bars[i] != NULL) {
            lv_obj_add_flag(o->bars[i], LV_OBJ_FLAG_HIDDEN);
        }
    }
}

static void build_status(void)
{
    screen_objs_t *o = &s_objs[LOOK_STATUS];
    for (int i = 0; i < LOOK_STATUS_ROWS; i++) {
        const look_box_t *b = look_box(LOOK_STATUS, (look_item_t)(LOOK_ITEM_STATUS_1 + i));
        o->status_label[i] = label_at(o->root, b->x, b->y, b->w, b->h, b->size, LOOK_ALIGN_LEFT, b->colour);
        o->status_value[i] = label_at(o->root, b->x, b->y, b->w, b->h, b->size, LOOK_ALIGN_RIGHT, b->colour);
        if (o->status_label[i] != NULL) {
            lv_label_set_text(o->status_label[i], view_status_label((unsigned)i));
        }
    }
}

bool face_draw_init(scr_t *scr)
{
    s_scr = scr;
    s_ok = true;
    lv_obj_t *top = lv_screen_active();
    lv_obj_clean(top);
    lv_obj_set_style_bg_color(top, colour(LOOK_BG), 0);
    lv_obj_set_style_bg_opa(top, LV_OPA_COVER, 0);
    lv_obj_remove_flag(top, LV_OBJ_FLAG_SCROLLABLE);
    for (int screen = 0; screen < LOOK_SCREEN_COUNT; screen++) {
        build_root((look_screen_t)screen);
        if (s_objs[screen].root == NULL) {
            return false;
        }
    }
    build_home(LOOK_HOME);
    build_home(LOOK_LOGGED);
    build_medication();
    build_session();
    build_status();
    for (int screen = 0; screen < LOOK_SCREEN_COUNT; screen++) {
        if (screen != LOOK_HOME) {
            lv_obj_add_flag(s_objs[screen].root, LV_OBJ_FLAG_HIDDEN);
        }
    }
    s_shown = LOOK_HOME;
    return s_ok;
}

/* ----------------------------------------------------------------- view */

static void draw_blocks(const view_t *v)
{
    screen_objs_t *o = &s_objs[LOOK_SESSION];
    const look_box_t *area = look_box(LOOK_SESSION, LOOK_ITEM_BLOCKS);
    for (uint32_t i = 0; i < SHARE_BLOCKS; i++) {
        if (o->columns[i] == NULL || o->bars[i] == NULL) {
            continue;
        }
        bool kept = i < v->block_count;
        bool hollow = kept && v->hollow[i];
        lv_obj_set_flag(o->columns[i], LV_OBJ_FLAG_HIDDEN, !hollow);
        lv_obj_set_flag(o->bars[i], LV_OBJ_FLAG_HIDDEN, !kept || hollow);
        if (kept && !hollow) {
            int percent = v->block_percent[i] < 0 ? 0 : v->block_percent[i];
            int h = (area->h * percent + 50) / 100;
            h = h < BAR_MIN ? BAR_MIN : h;
            lv_obj_set_y(o->bars[i], area->y + area->h - h);
            lv_obj_set_height(o->bars[i], h);
        }
    }
}

void face_draw_view(const view_t *v)
{
    s_tone_on = v->tone_on;
    for (int k = 0; k < 2; k++) {
        look_screen_t screen = k == 0 ? LOOK_HOME : LOOK_LOGGED;
        screen_objs_t *o = &s_objs[screen];
        set_text(o->time, screen, LOOK_ITEM_TIME, v->time, NULL);
        set_text(o->date, screen, LOOK_ITEM_DATE, v->date, NULL);
        if (o->battery != NULL && strcmp(lv_label_get_text(o->battery), v->battery) != 0) {
            lv_label_set_text(o->battery, v->battery);
        }
    }
    screen_objs_t *home = &s_objs[LOOK_HOME];
    set_text(home->line, LOOK_HOME, LOOK_ITEM_LINE, v->last_tremor, NULL);
    set_text(s_objs[LOOK_LOGGED].line, LOOK_LOGGED, LOOK_ITEM_LINE, v->logged_next.text, &v->logged_next);
    if (!s_have_face || v->face != s_face) {
        const look_state_t *l = look_state(v->face);
        style_circle(home, l);
        if (s_have_face) {
            start_pulse(home->pulse, l->circle);
        }
        s_have_face = true;
        s_face = v->face;
    }

    screen_objs_t *med = &s_objs[LOOK_MEDICATION];
    set_text(med->label_1, LOOK_MEDICATION, LOOK_ITEM_DOSE_LABEL_1, v->label_1, NULL);
    set_text(med->value_1, LOOK_MEDICATION, LOOK_ITEM_DOSE_VALUE_1, v->value_1.text, &v->value_1);
    set_text_colour(med->value_1, v->due ? LOOK_DOSE : LOOK_TEXT);
    set_text(med->label_2, LOOK_MEDICATION, LOOK_ITEM_DOSE_LABEL_2, v->label_2, NULL);
    set_text(med->value_2, LOOK_MEDICATION, LOOK_ITEM_DOSE_VALUE_2, v->value_2.text, &v->value_2);

    screen_objs_t *ses = &s_objs[LOOK_SESSION];
    set_text(ses->share, LOOK_SESSION, LOOK_ITEM_SHARE, v->share, NULL);
    set_text(ses->share_line, LOOK_SESSION, LOOK_ITEM_SHARE_LINE, v->share_line, NULL);
    set_text(ses->blocks_left, LOOK_SESSION, LOOK_ITEM_BLOCKS_LEFT, v->blocks_left, NULL);
    set_text(ses->blocks_right, LOOK_SESSION, LOOK_ITEM_BLOCKS_RIGHT, v->blocks_right, NULL);
    draw_blocks(v);

    screen_objs_t *st = &s_objs[LOOK_STATUS];
    for (int i = 0; i < LOOK_STATUS_ROWS; i++) {
        lv_obj_t *value = st->status_value[i];
        if (value != NULL && strcmp(lv_label_get_text(value), v->status[i]) != 0) {
            lv_label_set_text(value, v->status[i]);
        }
    }
}

void face_draw_show(look_screen_t screen, int64_t now_us)
{
    if (screen == s_shown || now_us < s_hold_until_us || (unsigned)screen >= LOOK_SCREEN_COUNT) {
        return;
    }
    lv_obj_add_flag(s_objs[s_shown].root, LV_OBJ_FLAG_HIDDEN);
    lv_obj_remove_flag(s_objs[screen].root, LV_OBJ_FLAG_HIDDEN);
    s_shown = screen;
    if (screen == LOOK_LOGGED) {
        start_logged();
    }
}

look_screen_t face_draw_shown(void)
{
    return s_shown;
}

uint32_t face_draw_taps(void)
{
    return s_taps;
}

uint32_t face_draw_mismatches(void)
{
    return s_mismatches;
}

/* ---------------------------------------------------------------- taps */

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

/* on_click() runs in LVGL's port task, which holds the display lock. */
static void on_click(lv_event_t *e)
{
    look_screen_t screen = (look_screen_t)(intptr_t)lv_event_get_user_data(e);
    lv_point_t point = {0};
    lv_indev_t *indev = lv_indev_active();
    if (indev != NULL) {
        lv_indev_get_point(indev, &point);
    }
    int64_t now_us = esp_timer_get_time();
    s_taps++;
    if (s_scr == NULL || screen != s_shown) {
        usb_send("TOUCH at_us=%lld x=%ld y=%ld screen=%s target=none accepted=0", (long long)now_us,
                 (long)point.x, (long)point.y, screen_name(screen));
        return;
    }
    const look_box_t *tap = look_tap_box(screen);
    bool on_target = tap != NULL && point.x >= tap->x && point.x < tap->x + tap->w && point.y >= tap->y &&
                     point.y < tap->y + tap->h;
    const char *target = !on_target ? "none" : screen == LOOK_HOME ? "home" : "took_it";
    unsigned flags = scr_tap(s_scr, (int)point.x, (int)point.y, now_us);
    if ((flags & SCR_ACCEPTED) != 0) {
        press(screen == LOOK_HOME ? s_objs[LOOK_HOME].card : s_objs[LOOK_MEDICATION].button);
        s_hold_until_us = now_us + PRESS_US;
        if (s_tone_on) {
            tone_out_start(TONE_TAP);
        }
    }
    if ((flags & SCR_TOOK_IT) != 0) {
        screen_took_it(now_us);
    }
    usb_send("TOUCH at_us=%lld x=%ld y=%ld screen=%s target=%s accepted=%d", (long long)now_us, (long)point.x,
             (long)point.y, screen_name(screen), target, (flags & SCR_ACCEPTED) != 0 ? 1 : 0);
}
