/*
 * look.c holds the face's colours, its layout, and the text measures.
 * look.h describes them, and feature 11's requirements 42 to 46, 51, and 61
 * give the details.
 */

#include "look.h"

#include <string.h>

#include "face_metrics.h"

#define DOTS "..."

/* The circle's centre on Home and Logged. */
#define CIRCLE_X 75
#define CIRCLE_Y 146
#define CIRCLE_CX (CIRCLE_X + LOOK_CIRCLE / 2)
#define CIRCLE_CY (CIRCLE_Y + LOOK_CIRCLE / 2)
/* The word box is as wide as "Arm moving" at 40 pixels, the widest state
 * word. The icon sits on top of the word, and both keep every corner at least
 * 10 pixels inside the circle's edge. */
#define WORD_W 232
#define ICON_Y (CIRCLE_CY - 97)
#define WORD_Y (CIRCLE_CY - 9)

static const look_state_t STATES[] = {
    [FACE_TREMOR] = {true, LOOK_TREMOR, LOOK_WHITE, LOOK_ICON_TREMOR, "Tremor"},
    [FACE_NO_TREMOR] = {true, LOOK_NO_TREMOR, LOOK_WHITE, LOOK_ICON_NO_TREMOR, "No tremor"},
    [FACE_ARM_MOVING] = {false, LOOK_ARM, LOOK_TEXT, LOOK_ICON_ARM_MOVING, "Arm moving"},
    [FACE_WAITING] = {false, LOOK_WAITING, LOOK_TEXT, LOOK_ICON_WAITING, "Waiting"},
    [FACE_DOSE_DUE] = {true, LOOK_DOSE, LOOK_WHITE, LOOK_ICON_DOSE_DUE, "Dose due"},
};

static const look_state_t LOGGED = {true, LOOK_TOOK_IT, LOOK_WHITE, LOOK_ICON_LOGGED_RING, "Logged"};

#define TEXT(x_, y_, w_, size_, smallest_, align_, colour_) \
    {(x_), (y_), (w_), FACE_LINE_##size_, LOOK_KIND_TEXT, (size_), (smallest_), (align_), (colour_)}
#define SHAPE(x_, y_, w_, h_, colour_) {(x_), (y_), (w_), (h_), LOOK_KIND_SHAPE, 0, 0, LOOK_ALIGN_LEFT, (colour_)}
#define ICON(x_, y_, colour_) \
    {(x_), (y_), LOOK_ICON_PX, LOOK_ICON_PX, LOOK_KIND_ICON, 0, 0, LOOK_ALIGN_CENTER, (colour_)}
#define BATTERY {316, 58, 88, 40, LOOK_KIND_BATTERY, 28, 28, LOOK_ALIGN_CENTER, LOOK_TEXT}
#define STATUS_ROW(i) [LOOK_ITEM_STATUS_1 + (i)] = TEXT(34, 64 + 42 * (i), 342, 28, 28, LOOK_ALIGN_LEFT, LOOK_TEXT)

/* The Home layout, which the Logged view shares. The circle and its icon
 * and word take their colours from look_state(). */
#define HOME_ITEMS                                                                      \
    [LOOK_ITEM_CARD] = SHAPE(14, 138, 382, 314, LOOK_CARD),                             \
    [LOOK_ITEM_TIME] = TEXT(22, 26, 290, 96, 96, LOOK_ALIGN_LEFT, LOOK_TEXT),           \
    [LOOK_ITEM_DATE] = TEXT(22, 100, 200, 28, 28, LOOK_ALIGN_LEFT, LOOK_TEXT2),         \
    [LOOK_ITEM_BATTERY] = BATTERY,                                                      \
    [LOOK_ITEM_CIRCLE] = SHAPE(CIRCLE_X, CIRCLE_Y, LOOK_CIRCLE, LOOK_CIRCLE, 0),        \
    [LOOK_ITEM_CIRCLE_ICON] = ICON(CIRCLE_CX - LOOK_ICON_PX / 2, ICON_Y, 0),            \
    [LOOK_ITEM_CIRCLE_WORD] = TEXT(CIRCLE_CX - WORD_W / 2, WORD_Y, WORD_W, 40, 40, LOOK_ALIGN_CENTER, 0), \
    [LOOK_ITEM_LINE] = TEXT(12, 412, 386, 28, 28, LOOK_ALIGN_CENTER, LOOK_TEXT2)

static const look_box_t BOXES[LOOK_SCREEN_COUNT][LOOK_ITEM_COUNT] = {
    [LOOK_HOME] = {HOME_ITEMS},
    [LOOK_LOGGED] = {HOME_ITEMS},
    [LOOK_MEDICATION] = {
        [LOOK_ITEM_CARD] = SHAPE(14, 20, 382, 216, LOOK_CARD),
        [LOOK_ITEM_DOSE_LABEL_1] = TEXT(34, 40, 342, 28, 28, LOOK_ALIGN_LEFT, LOOK_TEXT2),
        [LOOK_ITEM_DOSE_VALUE_1] = TEXT(34, 72, 342, 40, 28, LOOK_ALIGN_LEFT, LOOK_TEXT),
        [LOOK_ITEM_DOSE_LABEL_2] = TEXT(34, 125, 342, 28, 28, LOOK_ALIGN_LEFT, LOOK_TEXT2),
        [LOOK_ITEM_DOSE_VALUE_2] = TEXT(34, 157, 342, 40, 28, LOOK_ALIGN_LEFT, LOOK_TEXT),
        [LOOK_ITEM_BUTTON] = SHAPE(0, LOOK_TOOK_IT_Y, LOOK_W, LOOK_H - LOOK_TOOK_IT_Y, LOOK_TOOK_IT),
        [LOOK_ITEM_BUTTON_ICON] = ICON(LOOK_W / 2 - LOOK_ICON_PX / 2, 294, LOOK_WHITE),
        [LOOK_ITEM_BUTTON_WORD] = TEXT(105, 396, 200, 56, 56, LOOK_ALIGN_CENTER, LOOK_WHITE),
    },
    [LOOK_SESSION] = {
        [LOOK_ITEM_SHARE] = TEXT(24, 40, 362, 56, 40, LOOK_ALIGN_LEFT, LOOK_TEXT),
        [LOOK_ITEM_SHARE_LINE] = TEXT(24, 101, 362, 28, 28, LOOK_ALIGN_LEFT, LOOK_TEXT2),
        [LOOK_ITEM_CARD] = SHAPE(14, 146, 382, 300, LOOK_CARD),
        [LOOK_ITEM_BLOCKS] = SHAPE(33, 166, 344, 210, LOOK_TREMOR),
        [LOOK_ITEM_BLOCKS_LEFT] = TEXT(33, 392, 165, 28, 28, LOOK_ALIGN_LEFT, LOOK_TEXT2),
        [LOOK_ITEM_BLOCKS_RIGHT] = TEXT(212, 392, 165, 28, 28, LOOK_ALIGN_RIGHT, LOOK_TEXT2),
    },
    [LOOK_STATUS] = {
        [LOOK_ITEM_CARD] = SHAPE(14, 40, 382, 422, LOOK_CARD),
        STATUS_ROW(0),
        STATUS_ROW(1),
        STATUS_ROW(2),
        STATUS_ROW(3),
        STATUS_ROW(4),
        STATUS_ROW(5),
        STATUS_ROW(6),
        STATUS_ROW(7),
        STATUS_ROW(8),
    },
};

static const look_box_t TAP_HOME = SHAPE(0, 0, LOOK_W, LOOK_H, 0);
static const look_box_t TAP_MEDICATION = SHAPE(0, LOOK_TOOK_IT_Y, LOOK_W, LOOK_H - LOOK_TOOK_IT_Y, 0);

const look_state_t *look_state(face_state_t s)
{
    switch (s) {
    case FACE_TREMOR:
    case FACE_NO_TREMOR:
    case FACE_ARM_MOVING:
    case FACE_WAITING:
    case FACE_DOSE_DUE:
        return &STATES[s];
    default:
        return &STATES[FACE_WAITING];
    }
}

const look_state_t *look_logged(void)
{
    return &LOGGED;
}

const look_box_t *look_box(look_screen_t screen, look_item_t item)
{
    if ((unsigned)screen >= LOOK_SCREEN_COUNT || (unsigned)item >= LOOK_ITEM_COUNT) {
        return NULL;
    }
    const look_box_t *b = &BOXES[screen][item];
    return b->w > 0 ? b : NULL;
}

const look_box_t *look_tap_box(look_screen_t screen)
{
    switch (screen) {
    case LOOK_HOME:
        return &TAP_HOME;
    case LOOK_MEDICATION:
        return &TAP_MEDICATION;
    default:
        return NULL;
    }
}

/* widths_of() gives the advance widths of a size, or NULL. */
static const uint8_t *widths_of(int size)
{
    switch (size) {
    case 28:
        return face_adv_28;
    case 40:
        return face_adv_40;
    case 56:
        return face_adv_56;
    case 96:
        return face_adv_96;
    default:
        return NULL;
    }
}

int look_line_height(int size)
{
    switch (size) {
    case 28:
        return FACE_LINE_28;
    case 40:
        return FACE_LINE_40;
    case 56:
        return FACE_LINE_56;
    case 96:
        return FACE_LINE_96;
    default:
        return 0;
    }
}

/* span_width() gives the width of n bytes of text, or -1. */
static int span_width(const char *text, size_t n, const uint8_t *widths)
{
    int sum = 0;
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)text[i];
        if (c < FACE_FIRST_CHAR || c > FACE_LAST_CHAR || widths[c - FACE_FIRST_CHAR] == 0) {
            return -1;
        }
        sum += widths[c - FACE_FIRST_CHAR];
    }
    return sum;
}

int look_text_width(const char *text, int size)
{
    const uint8_t *widths = widths_of(size);
    if (widths == NULL) {
        return -1;
    }
    return span_width(text, strlen(text), widths);
}

int look_fit_size(const char *text, int box_w, int largest, int smallest)
{
    static const int SIZES[] = {96, 56, 40, 28};
    for (size_t i = 0; i < sizeof SIZES / sizeof SIZES[0]; i++) {
        int size = SIZES[i];
        if (size > largest || size < smallest) {
            continue;
        }
        int w = look_text_width(text, size);
        if (w >= 0 && w <= box_w) {
            return size;
        }
    }
    return 0;
}

size_t look_cut(const char *text, size_t cut_at, size_t cut_len, int box_w, int size, char *out, size_t out_size)
{
    const uint8_t *widths = widths_of(size);
    size_t len = strlen(text);
    if (widths == NULL || out_size == 0) {
        return 0;
    }
    int whole = span_width(text, len, widths);
    if (whole >= 0 && whole <= box_w) {
        if (len + 1 > out_size) {
            return 0;
        }
        memcpy(out, text, len + 1);
        return len;
    }
    if (cut_at > len) {
        cut_at = len;
    }
    if (cut_len > len - cut_at) {
        cut_len = len - cut_at;
    }
    const char *tail = text + cut_at + cut_len;
    size_t tail_len = len - cut_at - cut_len;
    int fixed = span_width(text, cut_at, widths);
    int tail_w = span_width(tail, tail_len, widths);
    int dots_w = span_width(DOTS, strlen(DOTS), widths);
    if (fixed < 0 || tail_w < 0 || dots_w < 0) {
        return 0;
    }
    int room = box_w - fixed - tail_w - dots_w;
    if (room < 0) {
        return 0;
    }
    size_t keep = 0;
    int used = 0;
    while (keep < cut_len) {
        int w = span_width(text + cut_at + keep, 1, widths);
        if (w < 0 || used + w > room) {
            break;
        }
        used += w;
        keep++;
    }
    size_t total = cut_at + keep + strlen(DOTS) + tail_len;
    if (total + 1 > out_size) {
        return 0;
    }
    memcpy(out, text, cut_at + keep);
    memcpy(out + cut_at + keep, DOTS, strlen(DOTS));
    memcpy(out + cut_at + keep + strlen(DOTS), tail, tail_len);
    out[total] = '\0';
    return total;
}
