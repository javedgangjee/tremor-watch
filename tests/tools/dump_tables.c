/*
 * dump_tables.c prints every value in core/detector_tables.h, one value on each line.
 *
 * Each line holds a name, an index, and a value. Each number is in the %a
 * hexadecimal float form, which is exact, so Python reads back the same bits
 * with float.fromhex. A table with rows uses the index row * columns + column.
 * tests/tools/test_gen_tables.py compiles and runs this program.
 */
#include <stddef.h>
#include <stdio.h>

#include "detector_tables.h"

static void print_doubles(const char *name, const double *values, size_t count)
{
    for (size_t i = 0; i < count; i++) {
        printf("%s %zu %a\n", name, i, values[i]);
    }
}

static void print_floats(const char *name, const float *values, size_t count, size_t first)
{
    for (size_t i = 0; i < count; i++) {
        printf("%s %zu %a\n", name, first + i, (double)values[i]);
    }
}

int main(void)
{
    printf("DET_MODEL_SHA256 0 %s\n", DET_MODEL_SHA256);
    printf("DET_N_COEF 0 %d\n", DET_N_COEF);
    printf("DET_N_FILT 0 %d\n", DET_N_FILT);
    printf("DET_N_BINS 0 %d\n", DET_N_BINS);
    printf("DET_PSD_SEG 0 %d\n", DET_PSD_SEG);
    printf("DET_SPG_SEG 0 %d\n", DET_SPG_SEG);

    print_doubles("det_mean", det_mean, DET_N_COEF);
    print_doubles("det_scale", det_scale, DET_N_COEF);
    print_doubles("det_coef", det_coef, DET_N_COEF);
    print_doubles("det_intercept", &det_intercept, 1);
    print_doubles("det_threshold", &det_threshold, 1);

    print_floats("det_w_psd", det_w_psd, DET_PSD_SEG, 0);
    print_floats("det_w_spg", det_w_spg, DET_SPG_SEG, 0);
    for (size_t row = 0; row < DET_N_FILT; row++) {
        print_floats("det_filters", det_filters[row], DET_N_BINS, row * DET_N_BINS);
    }
    for (size_t row = 0; row < DET_N_COEF; row++) {
        print_floats("det_dct", det_dct[row], DET_N_FILT, row * DET_N_FILT);
    }
    return 0;
}
