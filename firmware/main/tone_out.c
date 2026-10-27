/*
 * tone_out.c drives the board's ES8311 audio codec. tone_out.h describes it.
 *
 * The I2S channel repeats the last data in its DMA buffers when nothing new
 * is written, so after each pattern the feed writes silence for longer than
 * the buffers hold. The first round of a pattern writes 60 milliseconds, so
 * the buffers keep a lead when a round comes late, and each later round
 * writes 20 milliseconds.
 */

#include "tone_out.h"

#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "bsp/esp-bsp.h"
#include "esp_codec_dev.h"

/* One round of the screen task lasts 20 milliseconds. */
#define ROUND_SAMPLES (TONE_RATE / 50)
/* The first round of a pattern writes three rounds. */
#define LEAD_ROUNDS 3
/* The silence after a pattern lasts 6 rounds, which is longer than the 90
 * milliseconds that the I2S DMA buffers hold. */
#define SILENCE_ROUNDS 6
#define VOLUME 60
#define NO_TONE (-1)

static esp_codec_dev_handle_t s_codec;
static atomic_int s_pending = NO_TONE;
static int s_kind = NO_TONE;
static size_t s_pos;
static int s_silence;
static int16_t s_samples[ROUND_SAMPLES * LEAD_ROUNDS];

bool tone_out_init(void)
{
    s_codec = bsp_audio_codec_speaker_init();
    if (s_codec == NULL) {
        return false;
    }
    esp_codec_dev_sample_info_t fs = {
        .bits_per_sample = 16,
        .channel = 1,
        .sample_rate = TONE_RATE,
    };
    if (esp_codec_dev_open(s_codec, &fs) != ESP_CODEC_DEV_OK) {
        s_codec = NULL;
        return false;
    }
    if (esp_codec_dev_set_out_vol(s_codec, VOLUME) != ESP_CODEC_DEV_OK) {
        s_codec = NULL;
        return false;
    }
    return true;
}

void tone_out_start(tone_kind_t kind)
{
    atomic_store(&s_pending, (int)kind);
}

int tone_out_feed(void)
{
    if (s_codec == NULL) {
        atomic_store(&s_pending, NO_TONE);
        return NO_TONE;
    }
    int started = atomic_exchange(&s_pending, NO_TONE);
    size_t want = ROUND_SAMPLES;
    if (started != NO_TONE) {
        s_kind = started;
        s_pos = 0;
        want = ROUND_SAMPLES * LEAD_ROUNDS;
    }
    if (s_kind != NO_TONE) {
        size_t n = tone_fill((tone_kind_t)s_kind, s_pos, s_samples, want);
        s_pos += n;
        if (n < want) {
            memset(s_samples + n, 0, (want - n) * sizeof s_samples[0]);
            s_kind = NO_TONE;
            s_silence = SILENCE_ROUNDS;
        }
        esp_codec_dev_write(s_codec, s_samples, (int)(want * sizeof s_samples[0]));
    } else if (s_silence > 0) {
        s_silence--;
        memset(s_samples, 0, ROUND_SAMPLES * sizeof s_samples[0]);
        esp_codec_dev_write(s_codec, s_samples, (int)(ROUND_SAMPLES * sizeof s_samples[0]));
    }
    return started;
}
