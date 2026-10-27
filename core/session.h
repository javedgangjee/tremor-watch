/*
 * session.h holds the state task's rules. It joins the session share, the
 * face state, and the doses, and it counts the answers.
 *
 * The state task passes every answer's code unchanged to face_answer(), and
 * to share_add() when the answer has a window. It calls face_gap() at each
 * stretch after the first, because every such stretch follows a gap. It ticks
 * the doses once a second and sets the face's dose due flag from the result.
 *
 * The caller owns the state. The file has no static data that changes.
 */

#ifndef SESSION_H
#define SESSION_H

#include <stdbool.h>
#include <stdint.h>

#include "dose.h"
#include "face.h"
#include "share.h"

/* A call sets this flag when the shown state changes. */
#define SESS_FACE_CHANGED 1u
/* sess_answer() sets this flag when the share counts the answer. */
#define SESS_COUNTED 2u
/* sess_tick() sets this flag when a dose becomes due, so the tone plays. */
#define SESS_TONE 4u
/* sess_took_it() sets this flag when it logs a dose. */
#define SESS_DOSE_LOGGED 8u

typedef struct {
    share_t share;
    face_t face;
    dose_t dose;
    /* The answers of the session by result code. */
    uint32_t answers[RES_COUNT];
    /* The stretches of the session that followed a gap. */
    uint32_t gaps;
    /* The changes of the shown state since sess_init(). */
    uint32_t face_changes;
} sess_t;

/* sess_init() clears the doses, the schedule, and the clock, starts the share
 * at now_us, sets the face to Waiting, and clears every count. */
void sess_init(sess_t *s, int64_t now_us);

/* sess_new_session() starts the share at now_us, sets the face to Waiting,
 * drops the doses, and clears the answer and gap counts. It keeps the schedule,
 * the clock, and the count of face changes. */
void sess_new_session(sess_t *s, int64_t now_us);

/* sess_stretch() takes the start of stretch `number`. For a number above 0 it
 * counts a gap and calls face_gap(). It returns the flags. */
unsigned sess_stretch(sess_t *s, uint32_t number);

/* sess_answer() takes one answer and returns the flags. window is the window
 * number when has_window is true. time_us is the time of the window's last
 * 100 Hz sample, or the time a fault answer became due. */
unsigned sess_answer(sess_t *s, bool has_window, uint32_t window, res_code_t code, int64_t time_us);

/* sess_tick() ticks the doses at now_us and returns the flags. */
unsigned sess_tick(sess_t *s, int64_t now_us);

/* sess_took_it() takes a "Took it" tap at now_us. It calls dose_took_it(),
 * and when that accepts, it clears the face's dose due flag. It returns 0 when
 * dose_took_it() refuses the tap. Otherwise it returns SESS_DOSE_LOGGED, with
 * SESS_FACE_CHANGED when the shown state changes. */
unsigned sess_took_it(sess_t *s, int64_t now_us);

#endif /* SESSION_H */
