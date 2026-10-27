/* session.c holds the state task's rules. See session.h. */

#include "session.h"

static void clear_counts(sess_t *s)
{
    for (int code = 0; code < RES_COUNT; code++) {
        s->answers[code] = 0;
    }
    s->gaps = 0;
}

/* Counts a change of the shown state and returns its flag. */
static unsigned changed(sess_t *s, bool change)
{
    if (!change) {
        return 0;
    }
    s->face_changes++;
    return SESS_FACE_CHANGED;
}

void sess_init(sess_t *s, int64_t now_us)
{
    dose_init(&s->dose);
    share_start(&s->share, now_us);
    face_init(&s->face);
    clear_counts(s);
    s->face_changes = 0;
}

void sess_new_session(sess_t *s, int64_t now_us)
{
    share_start(&s->share, now_us);
    face_init(&s->face);
    dose_new_session(&s->dose, now_us);
    clear_counts(s);
}

unsigned sess_stretch(sess_t *s, uint32_t number)
{
    if (number == 0) {
        return 0;
    }
    s->gaps++;
    return changed(s, face_gap(&s->face));
}

unsigned sess_answer(sess_t *s, bool has_window, uint32_t window, res_code_t code, int64_t time_us)
{
    unsigned flags = 0;
    if ((unsigned)code < RES_COUNT) {
        s->answers[code]++;
    }
    if (has_window && share_add(&s->share, window, code, time_us)) {
        flags |= SESS_COUNTED;
    }
    flags |= changed(s, face_answer(&s->face, code, time_us));
    return flags;
}

unsigned sess_tick(sess_t *s, int64_t now_us)
{
    unsigned due = dose_tick(&s->dose, now_us);
    unsigned flags = 0;
    if ((due & DOSE_BECAME_DUE) != 0) {
        flags |= changed(s, face_set_dose_due(&s->face, true));
        flags |= SESS_TONE;
    } else if ((due & DOSE_DUE_ENDED) != 0) {
        flags |= changed(s, face_set_dose_due(&s->face, false));
    }
    return flags;
}

unsigned sess_took_it(sess_t *s, int64_t now_us)
{
    if (!dose_took_it(&s->dose, now_us)) {
        return 0;
    }
    return SESS_DOSE_LOGGED | changed(s, face_set_dose_due(&s->face, false));
}
