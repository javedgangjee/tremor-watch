/*
 * screens.c holds the face's screen rules. screens.h describes them, and
 * feature 11's requirements 54 to 57 give the details.
 */

#include "screens.h"

/* show() moves to a screen at now_us. */
static unsigned show(scr_t *s, look_screen_t screen, int64_t now_us)
{
    s->screen = screen;
    s->shown_us = now_us;
    s->used_us = now_us;
    s->waiting = false;
    return SCR_CHANGED;
}

/* inside() is true when the point lies in the box. */
static bool inside(const look_box_t *b, int x, int y)
{
    return b != NULL && x >= b->x && x < b->x + b->w && y >= b->y && y < b->y + b->h;
}

void scr_init(scr_t *s, int64_t now_us)
{
    s->screen = LOOK_HOME;
    s->shown_us = now_us;
    s->used_us = now_us;
    s->waiting = false;
    s->waiting_us = 0;
    s->armed = false;
    s->down_reads = 0;
}

unsigned scr_tap(scr_t *s, int x, int y, int64_t now_us)
{
    /* Every tap counts as use, including a tap the screen ignores. */
    s->used_us = now_us;
    if (now_us - s->shown_us < SCR_SETTLE_US) {
        return 0;
    }
    if (!inside(look_tap_box(s->screen), x, y)) {
        return 0;
    }
    if (s->screen == LOOK_HOME) {
        return SCR_ACCEPTED | show(s, LOOK_MEDICATION, now_us);
    }
    /* The only other screen with a tap target is Medication. */
    if (s->waiting && now_us - s->waiting_us < SCR_WAIT_US) {
        return 0;
    }
    s->waiting = true;
    s->waiting_us = now_us;
    return SCR_ACCEPTED | SCR_TOOK_IT;
}

unsigned scr_button(scr_t *s, bool down, int64_t now_us)
{
    if (!down) {
        s->armed = true;
        s->down_reads = 0;
        return 0;
    }
    s->down_reads++;
    if (!s->armed || s->down_reads != 2) {
        return 0;
    }
    s->armed = false;
    switch (s->screen) {
    case LOOK_HOME:
        return show(s, LOOK_MEDICATION, now_us);
    case LOOK_MEDICATION:
    case LOOK_LOGGED:
        return show(s, LOOK_SESSION, now_us);
    case LOOK_SESSION:
        return show(s, LOOK_STATUS, now_us);
    default:
        return show(s, LOOK_HOME, now_us);
    }
}

unsigned scr_logged(scr_t *s, int64_t now_us)
{
    return show(s, LOOK_LOGGED, now_us);
}

unsigned scr_tick(scr_t *s, int64_t now_us)
{
    switch (s->screen) {
    case LOOK_HOME:
        return 0;
    case LOOK_LOGGED:
        return now_us - s->shown_us >= SCR_LOGGED_US ? show(s, LOOK_HOME, now_us) : 0u;
    default:
        return now_us - s->used_us >= SCR_IDLE_US ? show(s, LOOK_HOME, now_us) : 0u;
    }
}

look_screen_t scr_screen(const scr_t *s)
{
    return s->screen;
}
