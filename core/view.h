/*
 * view.h holds the texts and values that the face draws.
 *
 * The state task builds the view from the session once a second and after
 * each change, and it sends the view to the screen task, which only draws it.
 * The time is 24-hour, and the date is a short weekday, the day, and a short
 * month in English. Before the dose clock is set, the time shows "--:--".
 *
 * The caller owns the view. The file has no static data that changes.
 */

#ifndef VIEW_H
#define VIEW_H

#include <stdbool.h>
#include <stdint.h>

#include "face.h"
#include "look.h"
#include "session.h"
#include "share.h"

/* A text that may be cut holds this many bytes with its zero byte. */
#define VIEW_TEXT_MAX 48
/* The Tables row gives this many digits of the table hash. */
#define VIEW_HASH_DIGITS 8

/* view_cut_t is a text that may be too wide for its box. look_cut() cuts the
 * cut_len bytes from cut_at, which hold the medicine name. */
typedef struct {
    char text[VIEW_TEXT_MAX];
    uint8_t cut_at;
    uint8_t cut_len;
} view_cut_t;

typedef struct {
    /* The shown face state and whether a dose is due. */
    face_state_t face;
    bool due;
    /* Home's time, date and last tremor line. */
    char time[8];
    char date[16];
    char last_tremor[24];
    /* Medication's two entries. While a dose is due, the first value is the
     * due dose, which the face draws in purple. */
    char label_1[12];
    view_cut_t value_1;
    char label_2[12];
    view_cut_t value_2;
    /* The Logged view's next dose line. */
    view_cut_t logged_next;
    /* The next dose time and the last tremor time as short texts for the
     * SCREEN_VIEW line: "HH:MM", "--:--" with no clock, or "none". */
    char next_short[8];
    char last_tremor_short[8];
    /* Session's figure, its line, and the whole percent, or -1 before any
     * still window. */
    char share[16];
    char share_line[32];
    int percent;
    /* The blocks from the oldest kept one. A block's percent is -1 when it
     * has no still window. */
    uint32_t block_count;
    bool hollow[SHARE_BLOCKS];
    int block_percent[SHARE_BLOCKS];
    /* The labels under the blocks: the oldest block's start time and "Now". */
    char blocks_left[8];
    char blocks_right[8];
    /* The nine status values in the order of view_status_label(). */
    char status[LOOK_STATUS_ROWS][16];
    /* The tone setting, the count of dose tones, and the count of accepted
     * doses since boot. The screen task plays the dose tone when the first
     * count rises and shows the Logged view when the second rises. */
    bool tone_on;
    uint32_t dose_tones;
    uint32_t doses_accepted;
} view_t;

typedef struct {
    /* battery_known is false when the power chip reports no battery. */
    bool battery_known;
    uint32_t battery_mv;
    int battery_percent;
    uint32_t uptime_s;
    /* has_answer is true once an answer has come. The last answer's stretch,
     * its stretch's rate in millionths of a reading per second, which is 0
     * while the stretch has no rate, and its detector run time. */
    bool has_answer;
    uint32_t stretch;
    uint32_t rate_uhz;
    int64_t run_us;
    bool recording;
    uint32_t firmware;
    /* The table hash as hexadecimal digits. */
    const char *hash;
    bool tone_on;
    uint32_t dose_tones;
    uint32_t doses_accepted;
} view_input_t;

/* view_status_label() gives the label of status row `row`, or "" for a row
 * past the ninth. */
const char *view_status_label(unsigned row);

/* view_build() fills the view from the session and the input at now_us. */
void view_build(view_t *v, const sess_t *s, const view_input_t *in, int64_t now_us);

#endif /* VIEW_H */
