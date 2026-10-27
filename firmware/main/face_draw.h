/*
 * face_draw.h builds and changes the LVGL objects of the face. Only
 * face_draw.c and screen_task.c call LVGL.
 *
 * face_draw_init() builds every object of the five screens once, from the
 * boxes of core/look.h, and shows Home. face_draw_view() changes only the
 * texts and objects whose values changed. face_draw_show() shows the screen
 * that core/screens.c gives. The click event of each screen gives the point
 * to scr_tap() and acts on its flags.
 *
 * Every function here runs while the caller holds the display lock. The
 * click event runs in LVGL's port task, which holds the lock too.
 */

#ifndef FACE_DRAW_H
#define FACE_DRAW_H

#include <stdbool.h>
#include <stdint.h>

#include "look.h"
#include "screens.h"
#include "view.h"

/* face_draw_init() builds the face. scr is the screen task's screen state,
 * which the click event uses under the display lock. It returns false when an
 * object could not be made. */
bool face_draw_init(scr_t *scr);

/* face_draw_view() draws a new view. */
void face_draw_view(const view_t *v);

/* face_draw_show() shows a screen at now_us. While a pressed card springs
 * back, the screen that shows stays until the press ends. */
void face_draw_show(look_screen_t screen, int64_t now_us);

/* face_draw_shown() gives the screen that shows. */
look_screen_t face_draw_shown(void);

/* face_draw_taps() gives the taps since boot, and face_draw_mismatches() the
 * texts whose LVGL width differed from the width of core/look.h. */
uint32_t face_draw_taps(void);
uint32_t face_draw_mismatches(void);

#endif /* FACE_DRAW_H */
