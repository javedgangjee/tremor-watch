/*
 * detector.c is the tremor detector in C.
 *
 * It follows detect() in reference/plain_detector.py in its 32-bit float case,
 * step for step. Every step before the score runs in 32-bit floats, as numpy
 * does on float32 arrays. The score runs in 64-bit doubles, because numpy
 * turns the 12 numbers into 64-bit values when it subtracts the 64-bit means.
 *
 * The fixed numbers come from detector_tables.h, made by tools/gen_tables.py.
 * Only this file in core/ includes that header, because it holds static
 * arrays.
 * det_init() builds both KISS FFT configurations in static buffers, so the
 * FFTs never touch the heap.
 *
 * The tremor detector comes from ParaDigMa by the Radboud Parkinson's group,
 * which has an Apache 2.0 licence. The source paper is Timmermans and
 * colleagues, npj Parkinson's Disease, 2025.
 */

#include "detector.h"

#include <math.h>
#include <stddef.h>

#include "detector_tables.h"
#include "kissfft/kiss_fftr.h"

_Static_assert(DET_MFCC_COUNT == DET_N_COEF, "the result must hold one value for each model number");
_Static_assert(DET_WINDOW_LEN == 400, "the window must hold 400 readings");

/*
 * Recipe numbers that detector_tables.h does not hold. Each comment names the
 * TremorConfig setting that gives the number, or the toolbox function that
 * holds it.
 */

/* sampling_frequency is 100 readings a second. */
#define DET_FS 100.0

/* The fine spectrum uses a 400 point FFT, which is sampling_frequency divided
 * by spectral_resolution_psd (0.25 Hz). Its slices of segment_length_psd_s
 * (3 s, 300 readings) start 60 readings apart, because overlap_fraction is 0.8. */
#define PSD_NFFT 400
#define PSD_BINS (PSD_NFFT / 2 + 1)
#define PSD_STEP 60
#define PSD_SLICES ((DET_WINDOW_LEN - DET_PSD_SEG) / PSD_STEP + 1)

/* The coarse spectrum uses a 200 point FFT, which is sampling_frequency divided
 * by spectral_resolution_spectrogram (0.5 Hz). Its slices of
 * segment_length_spectrogram_s (2 s, 200 readings) start 40 readings apart,
 * because overlap_fraction is 0.8. */
#define SPG_NFFT 200
#define SPG_STEP 40
#define SPG_SLICES ((DET_WINDOW_LEN - DET_SPG_SEG) / SPG_STEP + 1)

/* extract_spectral_domain_features multiplies the coarse spectrum by 100. */
#define SPG_GAIN 100.0f

/* compute_mfccs adds 1e-10 before it takes log10. */
#define LOG_FLOOR 1e-10f

/* spectral_resolution_psd is 0.25 Hz, which is the width of one fine step. */
#define PSD_STEP_HZ 0.25

/* fmin_peak_search is 1 Hz and fmax_peak_search is 25 Hz, both included.
 * They are fine steps 4 and 100. */
#define PEAK_FIRST_STEP 4
#define PEAK_LAST_STEP 100

/* fmin_below_rest_tremor is 0.5 Hz and fmax_below_rest_tremor is 3 Hz, which
 * is left out. They give fine steps 2 to 11. */
#define BELOW_FIRST_STEP 2
#define BELOW_LAST_STEP 11

/* movement_threshold is 50. The arm is at rest when the low-frequency sum is
 * 50 or less. */
#define MOVEMENT_THRESHOLD 50.0

/* fmin_rest_tremor is 3 Hz and fmax_rest_tremor is 7 Hz, both included. */
#define REST_TREMOR_MIN_HZ 3.0f
#define REST_TREMOR_MAX_HZ 7.0f

_Static_assert(SPG_NFFT / 2 + 1 == DET_N_BINS, "the filter table must cover every coarse step");
_Static_assert(PSD_SLICES == 2, "the fine spectrum must average two slices");
_Static_assert(SPG_SLICES == 6, "the coarse spectrum must keep six slices");

/* KISS FFT needs 4,288 bytes for 400 points and 2,288 bytes for 200 points on
 * a 64-bit laptop. det_init() checks the real sizes against these buffers. */
#define PSD_FFT_MEM 6144
#define SPG_FFT_MEM 3072

static _Alignas(max_align_t) unsigned char psd_fft_mem[PSD_FFT_MEM];
static _Alignas(max_align_t) unsigned char spg_fft_mem[SPG_FFT_MEM];
static kiss_fftr_cfg psd_fft;
static kiss_fftr_cfg spg_fft;

/* The scale of the fine spectrum and the factor that divides the coarse
 * spectrum by the sum of its window. det_init() sets both. */
static float psd_scale;
static float spg_recip;

/* Work buffers. They are static, so only one task may call det_run(). */
static float fft_in[PSD_NFFT];
static kiss_fft_cpx fft_out[PSD_BINS];
static float window_sq[DET_PSD_SEG];
static float psd[PSD_BINS];
static float spg[SPG_SLICES][DET_N_BINS];

/*
 * Adds n floats in the order that numpy's .sum() uses on a float32 array:
 * blocks of up to 128 values in eight running sums, and longer arrays split in
 * two. Keeping that order gives the same float as plain_detector.py.
 */
static float numpy_sum(const float *a, int n)
{
    if (n < 8) {
        float res = 0.0f;
        for (int i = 0; i < n; i++) {
            res += a[i];
        }
        return res;
    }
    if (n <= 128) {
        float r[8];
        int i;
        for (int j = 0; j < 8; j++) {
            r[j] = a[j];
        }
        for (i = 8; i < n - (n % 8); i += 8) {
            for (int j = 0; j < 8; j++) {
                r[j] += a[i + j];
            }
        }
        float res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        for (; i < n; i++) {
            res += a[i];
        }
        return res;
    }
    int n2 = n / 2;
    n2 -= n2 % 8;
    return numpy_sum(a, n2) + numpy_sum(a + n2, n - n2);
}

/* Builds one real FFT configuration in its static buffer, or returns NULL if
 * the buffer is too small. */
static kiss_fftr_cfg fft_config(int nfft, unsigned char *mem, size_t mem_size)
{
    size_t need = 0;
    (void)kiss_fftr_alloc(nfft, 0, NULL, &need);
    if (need == 0 || need > mem_size) {
        return NULL;
    }
    size_t len = mem_size;
    return kiss_fftr_alloc(nfft, 0, mem, &len);
}

bool det_init(void)
{
    psd_fft = fft_config(PSD_NFFT, psd_fft_mem, sizeof psd_fft_mem);
    spg_fft = fft_config(SPG_NFFT, spg_fft_mem, sizeof spg_fft_mem);
    if (psd_fft == NULL || spg_fft == NULL) {
        return false;
    }

    /* scale = 1.0 / (FS * float((w_psd * w_psd).sum())). numpy rounds the
     * scale to a float when it multiplies the float32 spectrum by it. */
    for (int i = 0; i < DET_PSD_SEG; i++) {
        window_sq[i] = det_w_psd[i] * det_w_psd[i];
    }
    psd_scale = (float)(1.0 / (DET_FS * (double)numpy_sum(window_sq, DET_PSD_SEG)));

    /* wsum = float(w_spg.sum()). numpy divides a complex64 value by wsum as a
     * multiply by the float 1 / wsum, so this keeps that factor. */
    spg_recip = 1.0f / numpy_sum(det_w_spg, DET_SPG_SEG);
    return true;
}

/* Step 1 of detect(): average two 3 s slices and add the three axes. */
static void fine_spectrum(const float window[DET_WINDOW_LEN][DET_AXES])
{
    for (int k = 0; k < PSD_BINS; k++) {
        psd[k] = 0.0f;
    }
    for (int axis = 0; axis < DET_AXES; axis++) {
        for (int s = 0; s < PSD_SLICES; s++) {
            for (int i = 0; i < DET_PSD_SEG; i++) {
                fft_in[i] = window[s * PSD_STEP + i][axis] * det_w_psd[i];
            }
            for (int i = DET_PSD_SEG; i < PSD_NFFT; i++) {
                fft_in[i] = 0.0f;
            }
            kiss_fftr(psd_fft, fft_in, fft_out);
            for (int k = 0; k < PSD_BINS; k++) {
                float p = (fft_out[k].r * fft_out[k].r + fft_out[k].i * fft_out[k].i) * psd_scale;
                if (k > 0 && k < PSD_BINS - 1) {
                    p *= 2.0f;
                }
                psd[k] += p / (float)PSD_SLICES;
            }
        }
    }
}

/* Step 2 of detect(): keep six 2 s slices apart and add the three axes. */
static void coarse_spectrum(const float window[DET_WINDOW_LEN][DET_AXES])
{
    for (int s = 0; s < SPG_SLICES; s++) {
        for (int k = 0; k < DET_N_BINS; k++) {
            spg[s][k] = 0.0f;
        }
    }
    for (int axis = 0; axis < DET_AXES; axis++) {
        for (int s = 0; s < SPG_SLICES; s++) {
            for (int i = 0; i < DET_SPG_SEG; i++) {
                fft_in[i] = window[s * SPG_STEP + i][axis] * det_w_spg[i];
            }
            kiss_fftr(spg_fft, fft_in, fft_out);
            for (int k = 0; k < DET_N_BINS; k++) {
                float re = fft_out[k].r * spg_recip;
                float im = fft_out[k].i * spg_recip;
                spg[s][k] += sqrtf(re * re + im * im) * SPG_GAIN;
            }
        }
    }
}

/* Step 3 of detect(): group each slice into 15 bands, take the log, apply the
 * cosine table, and average the six slices. */
static void shape_numbers(float mfcc[DET_N_COEF])
{
    float logb[DET_N_FILT];
    for (int i = 0; i < DET_N_COEF; i++) {
        mfcc[i] = 0.0f;
    }
    for (int s = 0; s < SPG_SLICES; s++) {
        for (int j = 0; j < DET_N_FILT; j++) {
            float band = 0.0f;
            for (int k = 0; k < DET_N_BINS; k++) {
                band += det_filters[j][k] * spg[s][k];
            }
            logb[j] = log10f(band + LOG_FLOOR);
        }
        for (int i = 0; i < DET_N_COEF; i++) {
            float sum = 0.0f;
            for (int j = 0; j < DET_N_FILT; j++) {
                sum += det_dct[i][j] * logb[j];
            }
            mfcc[i] += sum / (float)SPG_SLICES;
        }
    }
}

/* Step 4 of detect(): returns the probability, computed in 64-bit doubles. */
static double score(const float mfcc[DET_N_COEF])
{
    double dot = 0.0;
    for (int i = 0; i < DET_N_COEF; i++) {
        double z = ((double)mfcc[i] - det_mean[i]) / det_scale[i];
        dot += z * det_coef[i];
    }
    double total = dot + det_intercept;
    return 1.0 / (1.0 + exp(-total));
}

void det_run(const float window[DET_WINDOW_LEN][DET_AXES], det_result_t *out)
{
    fine_spectrum(window);
    coarse_spectrum(window);
    shape_numbers(out->mfcc);

    out->prob = score(out->mfcc);

    /* Step 5 of detect() finds the first largest fine step from 1 to 25 Hz, as argmax does. */
    int peak = PEAK_FIRST_STEP;
    for (int k = PEAK_FIRST_STEP + 1; k <= PEAK_LAST_STEP; k++) {
        if (psd[k] > psd[peak]) {
            peak = k;
        }
    }
    out->peak_hz = (float)peak * (float)PSD_STEP_HZ;

    /* Step 5 then adds the fine steps from 0.5 Hz up to 3 Hz in float and
     * multiplies the sum by 0.25 as a double. */
    float below_sum = numpy_sum(&psd[BELOW_FIRST_STEP], BELOW_LAST_STEP - BELOW_FIRST_STEP + 1);
    out->below = PSD_STEP_HZ * (double)below_sum;

    det_decide(out);
}

/* Steps 4 and 5 of detect() end with these three tests. */
void det_decide(det_result_t *r)
{
    r->logreg = r->prob >= det_threshold;
    r->at_rest = r->below <= MOVEMENT_THRESHOLD;

    /* The window is tremor only when all three checks pass. */
    r->tremor = r->logreg && r->peak_hz >= REST_TREMOR_MIN_HZ && r->peak_hz <= REST_TREMOR_MAX_HZ && r->at_rest;
}
