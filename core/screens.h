/*
 * screens.h holds the face's screen rules: which screen shows, which taps
 * count, the BOOT button, and when a screen goes back to Home.
 *
 * The rules follow the build spec's Watch face section, under Who wears it,
 * Behaviour, and Screens, with feature 11's requirements 54 to 57. Home takes
 * a tap anywhere and opens Medication. Medication takes a tap only in its
 * lower half, which asks the state task to log a dose. A screen ignores every
 * tap for 1 second after it appears, so a double tap on Home cannot log a
 * dose. After a "Took it" tap, Medication ignores taps until the state task
 * answers or 1 second passes. The Logged view shows for 3 seconds. Medication,
 * Session, and Status go back to Home 5 minutes after their last use, and
 * Home never times out.
 *
 * Times count in the watch's 64-bit microsecond timer. The caller owns the
 * state. The file has no static data that changes.
 */

#ifndef SCREENS_H
#define SCREENS_H

#include <stdbool.h>
#include <stdint.h>

#include "look.h"

/* A screen ignores taps for this long after it appears. */
#define SCR_SETTLE_US 1000000
/* After a "Took it" tap, Medication waits this long for the state task. */
#define SCR_WAIT_US 1000000
/* The Logged view shows for this long. */
#define SCR_LOGGED_US 3000000
/* Medication, Session, and Status go back to Home after this long unused. */
#define SCR_IDLE_US 300000000

/* A call sets this flag when a tap is accepted, so the card presses in and
 * the tap tone plays. */
#define SCR_ACCEPTED 1u
/* scr_tap() sets this flag when a "Took it" tap asks the state task for a
 * dose. */
#define SCR_TOOK_IT 2u
/* A call sets this flag when the screen changes. */
#define SCR_CHANGED 4u

typedef struct {
    look_screen_t screen;
    /* The time the screen appeared. */
    int64_t shown_us;
    /* The later of the time the screen appeared and its last tap or BOOT
     * press. */
    int64_t used_us;
    /* waiting is true from a "Took it" tap until the state task answers or
     * the wait ends. */
    bool waiting;
    int64_t waiting_us;
    /* armed is true after a read that found the BOOT button up. down_reads
     * counts the reads in a row that found it down. */
    bool armed;
    uint32_t down_reads;
} scr_t;

/* scr_init() shows Home at now_us. The BOOT button counts as not armed, so
 * holding it at start gives no press. */
void scr_init(scr_t *s, int64_t now_us);

/* scr_tap() takes a tap at the point (x, y) and returns the flags. */
unsigned scr_tap(scr_t *s, int x, int y, int64_t now_us);

/* scr_button() takes one read of the BOOT button, where down is true when it
 * is pressed, and returns the flags. A press counts on the second read in a
 * row that finds the button down after a read that found it up. A press moves
 * Home to Medication, Medication and Logged to Session, Session to Status, and
 * Status to Home. */
unsigned scr_button(scr_t *s, bool down, int64_t now_us);

/* scr_logged() shows the Logged view, because the state task accepted a dose.
 * It returns the flags. */
unsigned scr_logged(scr_t *s, int64_t now_us);

/* scr_tick() ends the Logged view and the screens left unused, and returns
 * the flags. */
unsigned scr_tick(scr_t *s, int64_t now_us);

/* scr_screen() gives the screen that shows. */
look_screen_t scr_screen(const scr_t *s);

#endif /* SCREENS_H */
