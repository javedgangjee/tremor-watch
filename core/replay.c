/*
 * replay runs the C detector on a PADS recording and prints one answer for
 * every window.
 *
 *     build/core/replay --pads FILE
 *
 * A PADS file has one reading on each line, with seven values. They are the
 * time, three accelerometer axes, and three gyroscope axes in radians per
 * second. replay converts the gyroscope to degrees per second as numpy's
 * degrees function does, rounds each value to a 32-bit float, and cuts the
 * first 50 rows, which hold the watch's start vibration. PADS is already at
 * 100 readings a second, so replay does no rate conversion.
 *
 * Window n holds rows 100n to 100n + 399 after the cut. replay prints a CSV
 * header and then one row for each window that fits, with the toolbox's
 * column names.
 */

#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "detector.h"

/* Every PADS file holds 1024 or 2048 rows, so 4096 rows leave room. */
#define MAX_ROWS 4096
#define PADS_VALUES 7
#define GYRO_FIRST 4
#define CUT_ROWS 50
#define WINDOW_STEP 100
#define LINE_MAX_CHARS 1024

/* numpy's degrees function multiplies by 180 / pi in 64-bit floats. */
#define RAD_TO_DEG (180.0 / 3.141592653589793)

static float rows[MAX_ROWS][DET_AXES];

/* read_line_values() reads the seven values of one line. It returns false if
 * the line holds fewer than seven numbers. */
static bool read_line_values(const char *line, double values[PADS_VALUES])
{
    const char *p = line;
    for (int v = 0; v < PADS_VALUES; v++) {
        char *end = NULL;
        errno = 0;
        values[v] = strtod(p, &end);
        if (end == p || errno == ERANGE) {
            return false;
        }
        p = end;
        while (*p == ' ' || *p == '\t') {
            p++;
        }
        if (v < PADS_VALUES - 1) {
            if (*p != ',') {
                return false;
            }
            p++;
        }
    }
    return true;
}

/* read_pads() reads the gyroscope of one file into rows. It returns the number
 * of rows, or -1 after it prints an error. */
static int read_pads(const char *path)
{
    FILE *file = fopen(path, "r");
    if (file == NULL) {
        fprintf(stderr, "replay: cannot read %s\n", path);
        return -1;
    }
    char line[LINE_MAX_CHARS];
    int n = 0;
    int line_no = 0;
    while (fgets(line, sizeof line, file) != NULL) {
        line_no++;
        size_t len = strlen(line);
        if (len == sizeof line - 1 && line[len - 1] != '\n') {
            fprintf(stderr, "replay: line %d of %s is too long\n", line_no, path);
            fclose(file);
            return -1;
        }
        if (strspn(line, " \t\r\n") == len) {
            continue;
        }
        double values[PADS_VALUES];
        if (!read_line_values(line, values)) {
            fprintf(stderr, "replay: line %d of %s has fewer than %d values\n", line_no, path, PADS_VALUES);
            fclose(file);
            return -1;
        }
        if (n == MAX_ROWS) {
            fprintf(stderr, "replay: %s has more than %d rows\n", path, MAX_ROWS);
            fclose(file);
            return -1;
        }
        for (int axis = 0; axis < DET_AXES; axis++) {
            rows[n][axis] = (float)(values[GYRO_FIRST + axis] * RAD_TO_DEG);
        }
        n++;
    }
    bool failed = ferror(file) != 0;
    fclose(file);
    if (failed) {
        fprintf(stderr, "replay: cannot read %s\n", path);
        return -1;
    }
    return n;
}

static void print_header(void)
{
    printf("window");
    for (int i = 1; i <= DET_MFCC_COUNT; i++) {
        printf(",mfcc_%d", i);
    }
    printf(",pred_tremor_proba,below_tremor_power,freq_peak,pred_arm_at_rest,pred_tremor_checked\n");
}

static void print_window(int index, const det_result_t *r)
{
    printf("%d", index);
    for (int i = 0; i < DET_MFCC_COUNT; i++) {
        printf(",%.9g", (double)r->mfcc[i]);
    }
    printf(",%.17g,%.17g,%.9g,%d,%d\n", r->prob, r->below, (double)r->peak_hz, r->at_rest ? 1 : 0,
           r->tremor ? 1 : 0);
}

int main(int argc, char **argv)
{
    if (argc != 3 || strcmp(argv[1], "--pads") != 0) {
        fprintf(stderr, "usage: replay --pads FILE\n");
        return 1;
    }
    if (!det_init()) {
        fprintf(stderr, "replay: det_init failed\n");
        return 1;
    }
    int n = read_pads(argv[2]);
    if (n < 0) {
        return 1;
    }

    print_header();
    int kept = n > CUT_ROWS ? n - CUT_ROWS : 0;
    for (int w = 0; w * WINDOW_STEP + DET_WINDOW_LEN <= kept; w++) {
        det_result_t r;
        const float(*window)[DET_AXES] = &rows[CUT_ROWS + w * WINDOW_STEP];
        det_run(window, &r);
        print_window(w, &r);
    }
    return 0;
}
