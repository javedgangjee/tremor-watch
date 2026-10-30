/*
 * look.h holds the face's colours, its layout, and the text measures.
 *
 * The look starts from the design file context/Tremor Watch Light.html. The
 * layout is a table of boxes in pixels for each screen. Each text box is as
 * tall as its font's line height in core/face_metrics.h, and each text and icon
 * box lies inside the screen's rounded shape. The text widths are the sums of
 * the advance widths in core/face_metrics.h, which is the width LVGL 9.5.0
 * gives with no kerning.
 *
 * The colours and the layout are const data, so the file has no static data
 * that changes.
 */

#ifndef LOOK_INCLUDED_H
#define LOOK_INCLUDED_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "face.h"

/* The screen is 410 by 502 pixels with corners of radius 60. */
#define LOOK_W 410
#define LOOK_H 502
#define LOOK_CORNER 60
/* The state circle is 260 pixels across, and an outline is 8 pixels wide. */
#define LOOK_CIRCLE 260
#define LOOK_OUTLINE 8
/* The "Took it" button is the lower half of Medication, from this row down. */
#define LOOK_TOOK_IT_Y 251
#define LOOK_CARD_RADIUS 40
/* The "Took it" check is this many pixels square. */
#define LOOK_ICON_PX 88
/* The circle's icons are this many pixels square, which leaves room under
 * them for a two-line word. */
#define LOOK_CIRCLE_ICON_PX 128

/* The colours as 0xRRGGBB values. */
#define LOOK_BG 0xF6F3EE
#define LOOK_CARD 0xFFFFFF
#define LOOK_TEXT 0x111315
#define LOOK_TEXT2 0x5C6265
#define LOOK_TREMOR 0x1B2E42
/* No tremor shows as "Rest" in a charcoal outline, and Arm moving as a
 * filled green circle. */
#define LOOK_ARM 0x2A7242
#define LOOK_DOSE 0x3F2559
#define LOOK_REST 0x26292B
#define LOOK_WAITING 0x5C6265
#define LOOK_TOOK_IT 0x173A28
#define LOOK_WHITE 0xFFFFFF

/* The screens. Logged is the view after a "Took it" tap, and it counts as
 * Medication for the BOOT button. */
typedef enum {
    LOOK_HOME = 0,
    LOOK_MEDICATION = 1,
    LOOK_LOGGED = 2,
    LOOK_SESSION = 3,
    LOOK_STATUS = 4,
    LOOK_SCREEN_COUNT = 5
} look_screen_t;

/* The icons, in the order of firmware/main/assets/face_icons.h. */
typedef enum {
    LOOK_ICON_TREMOR = 0,
    LOOK_ICON_NO_TREMOR = 1,
    LOOK_ICON_ARM_MOVING = 2,
    LOOK_ICON_WAITING = 3,
    LOOK_ICON_DOSE_DUE = 4,
    LOOK_ICON_CHECK = 5,
    LOOK_ICON_LOGGED_RING = 6,
    LOOK_ICON_LOGGED_TICK = 7,
    LOOK_ICON_COUNT = 8
} look_icon_t;

/* The items that a screen may hold. */
typedef enum {
    LOOK_ITEM_CARD = 0,
    LOOK_ITEM_TIME,
    LOOK_ITEM_DATE,
    LOOK_ITEM_CIRCLE,
    LOOK_ITEM_CIRCLE_ICON,
    LOOK_ITEM_CIRCLE_WORD,
    /* The second line of a two-line circle word. */
    LOOK_ITEM_CIRCLE_WORD_2,
    /* The last tremor line on Home, and the next dose line on Logged. */
    LOOK_ITEM_LINE,
    LOOK_ITEM_DOSE_LABEL_1,
    LOOK_ITEM_DOSE_VALUE_1,
    LOOK_ITEM_DOSE_LABEL_2,
    LOOK_ITEM_DOSE_VALUE_2,
    LOOK_ITEM_BUTTON,
    LOOK_ITEM_BUTTON_ICON,
    LOOK_ITEM_BUTTON_WORD,
    LOOK_ITEM_SHARE,
    LOOK_ITEM_SHARE_LINE,
    LOOK_ITEM_BLOCKS,
    LOOK_ITEM_BLOCKS_LEFT,
    LOOK_ITEM_BLOCKS_RIGHT,
    /* The nine status rows follow in order. Each row holds a label at the
     * left and a value at the right. */
    LOOK_ITEM_STATUS_1,
    LOOK_ITEM_STATUS_9 = LOOK_ITEM_STATUS_1 + 8,
    LOOK_ITEM_COUNT
} look_item_t;

#define LOOK_STATUS_ROWS 9

/* The kinds of box. A text box holds one line of text, an icon box one icon,
 * and a shape box a card, the circle, the button, or the blocks. */
typedef enum {
    LOOK_KIND_SHAPE = 0,
    LOOK_KIND_TEXT = 1,
    LOOK_KIND_ICON = 2
} look_kind_t;

typedef enum {
    LOOK_ALIGN_LEFT = 0,
    LOOK_ALIGN_CENTER = 1,
    LOOK_ALIGN_RIGHT = 2
} look_align_t;

typedef struct {
    int16_t x;
    int16_t y;
    int16_t w;
    int16_t h;
    look_kind_t kind;
    /* A text box's largest and smallest text size, or 0 for other boxes. */
    uint8_t size;
    uint8_t smallest;
    look_align_t align;
    /* The colour of the text, the icon, or the shape. */
    uint32_t colour;
} look_box_t;

typedef struct {
    /* filled is true for a filled circle and false for an outline. */
    bool filled;
    /* The colour of the fill or the outline. */
    uint32_t circle;
    /* The colour of the word and the icon. */
    uint32_t ink;
    look_icon_t icon;
    const char *word;
    /* The second line of the word, or NULL for a one-line word. */
    const char *word_2;
    /* spinner is true when a turning arc in the ink colour takes the icon's
     * place. Only Loading has it. */
    bool spinner;
    /* pulse is true when a change to this look pulses the circle. Rest and
     * Loading have no pulse. */
    bool pulse;
    /* bare is true when the circle has no fill and no outline, so only the
     * icon or spinner and the word show. Only Loading is bare. */
    bool bare;
} look_state_t;

/* look_state() gives the look of a face state, and the Waiting look for any
 * other value. Waiting shows the word "Loading" with a spinner. */
const look_state_t *look_state(face_state_t s);

/* look_logged() gives the look of the circle on the Logged view. */
const look_state_t *look_logged(void);

/* look_box() gives the box of an item on a screen, or NULL when the screen
 * lacks the item. */
const look_box_t *look_box(look_screen_t screen, look_item_t item);

/* look_bg() gives the background colour of a screen. Session and Status are
 * white, and the other screens use LOOK_BG. */
uint32_t look_bg(look_screen_t screen);

/* look_tap_box() gives the tap target of a screen, which is the whole screen
 * for Home and the lower half for Medication, or NULL for the others. */
const look_box_t *look_tap_box(look_screen_t screen);

/* look_line_height() gives the line height of a text size, or 0 for a size
 * that is not 22, 28, 32, 40, 56, or 96. */
int look_line_height(int size);

/* look_text_width() gives the width of a text in pixels. It gives -1 when the
 * text holds a character that the font lacks or the size is not 22, 28, 32,
 * 40, 56, or 96. */
int look_text_width(const char *text, int size);

/* look_fit_size() gives the largest of 96, 56, 40, 32, 28, and 22, from
 * largest down to smallest, at which the text fits in box_w, or 0. */
int look_fit_size(const char *text, int box_w, int largest, int smallest);

/* look_cut() copies the text into out when it fits in box_w at size.
 * Otherwise it keeps the part before cut_at and the part after
 * cut_at + cut_len, and it keeps the longest start of the cut part with "..."
 * after it that fits. It returns the length, or 0 when even an empty cut part
 * does not fit or the result does not fit in out_size. */
size_t look_cut(const char *text, size_t cut_at, size_t cut_len, int box_w, int size, char *out, size_t out_size);

#endif /* LOOK_INCLUDED_H */
