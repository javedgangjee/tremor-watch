/*
 * tone.h holds the samples of the face's two tones.
 *
 * The tap tone plays at each accepted tap. It is one 660 Hz tone of 120
 * milliseconds. The dose tone plays when a dose becomes due. It is three
 * 880 Hz tones of 250 milliseconds, each with 250 milliseconds of silence
 * after it. Each tone has an amplitude of 30
 * percent of full scale and a fade of 5 milliseconds at each end, so it is
 * soft and does not click.
 *
 * Each sample depends only on its number in the pattern, so the result does
 * not depend on how the caller splits the pattern. The file has no static
 * data that changes.
 */

#ifndef TONE_H
#define TONE_H

#include <stddef.h>
#include <stdint.h>

/* The tones play at 16000 samples a second in mono. */
#define TONE_RATE 16000
/* The peak is 30 percent of 32767, rounded down. */
#define TONE_PEAK 9830

typedef enum {
    TONE_TAP = 0,
    TONE_DOSE = 1
} tone_kind_t;

/* tone_length() gives the length of a pattern in samples, or 0 for an unknown
 * kind. */
size_t tone_length(tone_kind_t kind);

/* tone_fill() writes samples start to start + n - 1 of the pattern into out,
 * or fewer at its end, and returns the number written. */
size_t tone_fill(tone_kind_t kind, size_t start, int16_t *out, size_t n);

#endif /* TONE_H */
