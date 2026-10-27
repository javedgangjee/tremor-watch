/*
 * tone_out.h drives the board's ES8311 audio codec, which plays the face's
 * tones from core/tone.c. Only tone_out.c calls the codec.
 *
 * tone_out_init() starts the codec at 16000 samples a second in mono with 16
 * bits and sets the volume to 60. tone_out_start() asks for a pattern from any
 * task. The screen task calls tone_out_feed() once a round, and each call
 * writes the next 20 milliseconds, so a tone never stops the screen task for
 * more than one round. When no tone plays, the codec gets silence.
 */

#ifndef TONE_OUT_H
#define TONE_OUT_H

#include <stdbool.h>

#include "tone.h"

/* tone_out_init() starts the codec. It returns false when the codec did not
 * start, and then no tone plays. */
bool tone_out_init(void);

/* tone_out_start() asks for a pattern. A new pattern takes the place of one
 * that plays. */
void tone_out_start(tone_kind_t kind);

/* tone_out_feed() writes the next part of the pattern or of the silence after
 * it. It returns the kind of a pattern that it started in this call, or -1. */
int tone_out_feed(void);

#endif /* TONE_OUT_H */
