/*
 * face_metrics.h holds each face font's line height, base line, and the advance width of each character from space to ~ in whole pixels as LVGL 9.5.0 rounds it.
 * tools/gen_face_assets.py made this file. Do not edit it.
 * The command is `reference/.venv/bin/python tools/gen_face_assets.py`.
 */

#ifndef FACE_METRICS_H
#define FACE_METRICS_H

#include <stdint.h>

#define FACE_FIRST_CHAR 0x20
#define FACE_LAST_CHAR 0x7E

#define FACE_LINE_28 30
#define FACE_BASE_28 7
#define FACE_LINE_40 39
#define FACE_BASE_40 9
#define FACE_LINE_56 57
#define FACE_BASE_56 13
#define FACE_LINE_96 70
#define FACE_BASE_96 1

/* The advance widths at 28 pixels, where 0 marks a character the font lacks. */
static const uint8_t face_adv_28[95] = {
    6, 7, 12, 21, 17, 22, 19, 7, 12, 12, 13, 17, 7, 13, 7, 14,
    19, 10, 17, 17, 19, 17, 17, 17, 17, 18, 7, 7, 17, 17, 17, 15,
    22, 21, 19, 20, 21, 18, 18, 22, 21, 8, 18, 20, 18, 25, 21, 23,
    19, 23, 19, 18, 18, 20, 21, 26, 20, 20, 17, 11, 15, 11, 16, 14,
    17, 16, 18, 15, 18, 16, 12, 18, 17, 7, 7, 16, 7, 25, 17, 17,
    18, 18, 11, 14, 12, 17, 16, 22, 16, 16, 14, 12, 9, 12, 17,
};

/* The advance widths at 40 pixels, where 0 marks a character the font lacks. */
static const uint8_t face_adv_40[95] = {
    8, 10, 17, 30, 24, 32, 27, 10, 17, 17, 19, 24, 10, 18, 10, 21,
    27, 14, 24, 24, 27, 24, 24, 24, 24, 25, 10, 10, 24, 24, 24, 21,
    32, 29, 28, 29, 30, 26, 26, 32, 30, 11, 26, 28, 25, 35, 30, 33,
    27, 33, 27, 25, 26, 29, 29, 38, 28, 28, 25, 16, 21, 16, 23, 20,
    24, 22, 25, 21, 25, 23, 17, 25, 24, 10, 10, 23, 10, 36, 24, 25,
    25, 25, 16, 20, 17, 24, 23, 31, 22, 23, 20, 17, 13, 17, 24,
};

/* The advance widths at 56 pixels, where 0 marks a character the font lacks. */
static const uint8_t face_adv_56[95] = {
    11, 14, 24, 41, 34, 44, 38, 14, 23, 23, 27, 34, 14, 26, 14, 29,
    38, 20, 34, 34, 38, 34, 34, 34, 34, 36, 14, 14, 34, 34, 34, 29,
    44, 41, 39, 40, 41, 36, 36, 44, 41, 15, 36, 39, 35, 49, 42, 46,
    38, 46, 38, 35, 37, 41, 41, 53, 39, 40, 35, 22, 29, 22, 33, 28,
    34, 31, 35, 30, 35, 33, 24, 35, 33, 14, 14, 32, 14, 51, 33, 35,
    35, 35, 23, 28, 24, 33, 33, 43, 31, 32, 28, 24, 19, 24, 33,
};

/* The advance widths at 96 pixels, where 0 marks a character the font lacks. */
static const uint8_t face_adv_96[95] = {
    19, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 44, 0, 0,
    66, 34, 58, 58, 65, 58, 58, 58, 58, 61, 24, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};

#endif /* FACE_METRICS_H */
