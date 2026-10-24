/*
 * Unit tests for the face's colours, layout, and text measures in
 * core/look.c. They hold cases 1 to 12 of feature 11's validation.md.
 *
 * The contrast ratio is the WCAG 2 ratio of relative luminances. The colour
 * distance is the Euclidean distance in OKLab. Protan and deutan vision are
 * simulated at full strength in linear RGB with the matrices of Machado,
 * Oliveira, and Fernandes, 2009.
 */

#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "face_metrics.h"
#include "look.h"
#include "unity.h"

void setUp(void) {}

void tearDown(void) {}

/* ---------------------------------------------------------------- colour */

static double linear(uint32_t channel)
{
    double c = (double)channel / 255.0;
    return c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4);
}

static void to_linear(uint32_t rgb, double out[3])
{
    out[0] = linear((rgb >> 16) & 0xFF);
    out[1] = linear((rgb >> 8) & 0xFF);
    out[2] = linear(rgb & 0xFF);
}

static double luminance(uint32_t rgb)
{
    double c[3];
    to_linear(rgb, c);
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

static double contrast(uint32_t a, uint32_t b)
{
    double la = luminance(a);
    double lb = luminance(b);
    double hi = la > lb ? la : lb;
    double lo = la > lb ? lb : la;
    return (hi + 0.05) / (lo + 0.05);
}

typedef enum { VISION_NORMAL = 0, VISION_PROTAN = 1, VISION_DEUTAN = 2 } vision_t;

static const double MACHADO[3][3][3] = {
    [VISION_NORMAL] = {{1, 0, 0}, {0, 1, 0}, {0, 0, 1}},
    [VISION_PROTAN] = {{0.152286, 1.052583, -0.204868}, {0.114503, 0.786281, 0.099216},
                       {-0.003882, -0.048116, 1.051998}},
    [VISION_DEUTAN] = {{0.367322, 0.860646, -0.227968}, {0.280085, 0.672501, 0.047413},
                       {-0.011820, 0.042940, 0.968881}},
};

static void oklab(uint32_t rgb, vision_t vision, double lab[3])
{
    double c[3];
    double s[3];
    to_linear(rgb, c);
    for (int i = 0; i < 3; i++) {
        double v = 0.0;
        for (int j = 0; j < 3; j++) {
            v += MACHADO[vision][i][j] * c[j];
        }
        s[i] = v < 0.0 ? 0.0 : v > 1.0 ? 1.0 : v;
    }
    double l = cbrt(0.4122214708 * s[0] + 0.5363325363 * s[1] + 0.0514459929 * s[2]);
    double m = cbrt(0.2119034982 * s[0] + 0.6806995451 * s[1] + 0.1073969566 * s[2]);
    double q = cbrt(0.0883024619 * s[0] + 0.2817188376 * s[1] + 0.6299787005 * s[2]);
    lab[0] = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * q;
    lab[1] = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * q;
    lab[2] = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * q;
}

static double distance(uint32_t a, uint32_t b, vision_t vision)
{
    double la[3];
    double lb[3];
    oklab(a, vision, la);
    oklab(b, vision, lb);
    return sqrt((la[0] - lb[0]) * (la[0] - lb[0]) + (la[1] - lb[1]) * (la[1] - lb[1]) +
                (la[2] - lb[2]) * (la[2] - lb[2]));
}

static void test_1_contrast(void)
{
    static const uint32_t PAIRS[][2] = {
        {0x111315, 0xFFFFFF}, {0x111315, 0xF6F3EE}, {0x5C6265, 0xFFFFFF}, {0x5C6265, 0xF6F3EE},
        {0xFFFFFF, 0x1B2E42}, {0xFFFFFF, 0x2A7242}, {0xFFFFFF, 0x3F2559}, {0xFFFFFF, 0x173A28},
        {0x3F2559, 0xFFFFFF}, {0x1B2E42, 0xFFFFFF}, {0x26292B, 0xFFFFFF}, {0x5C6265, 0xFFFFFF},
    };
    for (size_t i = 0; i < sizeof PAIRS / sizeof PAIRS[0]; i++) {
        TEST_ASSERT_TRUE_MESSAGE(contrast(PAIRS[i][0], PAIRS[i][1]) >= 3.0, "a pair is under 3 to 1");
    }
    TEST_ASSERT_DOUBLE_WITHIN(1e-9, 21.0, contrast(0x000000, 0xFFFFFF));
    TEST_ASSERT_DOUBLE_WITHIN(0.01, 5.86, contrast(0xFFFFFF, 0x2A7242));
    /* The look uses the same colours. */
    TEST_ASSERT_EQUAL_HEX32(0x3F2559, LOOK_DOSE);
    TEST_ASSERT_EQUAL_HEX32(0xF6F3EE, LOOK_BG);
    TEST_ASSERT_EQUAL_HEX32(0xFFFFFF, LOOK_CARD);
}

static void test_2_distance(void)
{
    static const uint32_t PAIRS[][2] = {
        {0x1B2E42, 0x2A7242}, {0x2A7242, 0x3F2559}, {0x26292B, 0x5C6265}, {0x2A7242, 0x173A28},
    };
    for (size_t i = 0; i < sizeof PAIRS / sizeof PAIRS[0]; i++) {
        for (int v = VISION_NORMAL; v <= VISION_DEUTAN; v++) {
            TEST_ASSERT_TRUE_MESSAGE(distance(PAIRS[i][0], PAIRS[i][1], (vision_t)v) >= 0.10,
                                     "a pair is under 0.10 apart");
        }
    }
    /* The Dose due and Tremor pair is left out, because the user chose the
     * design's purple. Its deutan distance is below 0.05. */
    TEST_ASSERT_TRUE(distance(0x1B2E42, 0x3F2559, VISION_DEUTAN) < 0.05);
}

static void check_state(face_state_t s, bool filled, uint32_t circle, uint32_t ink, look_icon_t icon,
                        const char *word)
{
    const look_state_t *l = look_state(s);
    TEST_ASSERT_EQUAL(filled, l->filled);
    TEST_ASSERT_EQUAL_HEX32(circle, l->circle);
    TEST_ASSERT_EQUAL_HEX32(ink, l->ink);
    TEST_ASSERT_EQUAL_INT(icon, l->icon);
    TEST_ASSERT_EQUAL_STRING(word, l->word);
}

static void test_3_states(void)
{
    check_state(FACE_TREMOR, true, 0x1B2E42, 0xFFFFFF, LOOK_ICON_TREMOR, "Tremor");
    check_state(FACE_NO_TREMOR, true, 0x2A7242, 0xFFFFFF, LOOK_ICON_NO_TREMOR, "No tremor");
    check_state(FACE_ARM_MOVING, false, 0x26292B, 0x111315, LOOK_ICON_ARM_MOVING, "Arm moving");
    check_state(FACE_WAITING, false, 0x5C6265, 0x111315, LOOK_ICON_WAITING, "Waiting");
    check_state(FACE_DOSE_DUE, true, 0x3F2559, 0xFFFFFF, LOOK_ICON_DOSE_DUE, "Dose due");
    check_state((face_state_t)9, false, 0x5C6265, 0x111315, LOOK_ICON_WAITING, "Waiting");
    for (int s = 0; s <= 9; s++) {
        const char *word = look_state((face_state_t)s)->word;
        TEST_ASSERT_TRUE(strcmp(word, "Dyskinesia") != 0);
        TEST_ASSERT_TRUE(strcmp(word, "No link") != 0);
        TEST_ASSERT_TRUE(strcmp(word, "Idle") != 0);
    }
}

/* ---------------------------------------------------------------- layout */

static void test_4_text_sizes(void)
{
    for (int screen = 0; screen < LOOK_SCREEN_COUNT; screen++) {
        for (int item = 0; item < LOOK_ITEM_COUNT; item++) {
            const look_box_t *b = look_box((look_screen_t)screen, (look_item_t)item);
            if (b == NULL || b->kind != LOOK_KIND_TEXT) {
                continue;
            }
            TEST_ASSERT_TRUE(b->size == 28 || b->size == 40 || b->size == 56 || b->size == 96);
            TEST_ASSERT_TRUE(b->smallest >= 28 && b->smallest <= b->size);
            TEST_ASSERT_EQUAL_INT(look_line_height(b->size), b->h);
        }
    }
}

/* in_shape() is true when the point lies in the 410 by 502 rectangle with
 * corners of radius 60. */
static bool in_shape(double x, double y)
{
    if (x < 0 || y < 0 || x > LOOK_W || y > LOOK_H) {
        return false;
    }
    double cx = x < LOOK_CORNER ? LOOK_CORNER : x > LOOK_W - LOOK_CORNER ? LOOK_W - LOOK_CORNER : x;
    double cy = y < LOOK_CORNER ? LOOK_CORNER : y > LOOK_H - LOOK_CORNER ? LOOK_H - LOOK_CORNER : y;
    return (x - cx) * (x - cx) + (y - cy) * (y - cy) <= (double)LOOK_CORNER * LOOK_CORNER;
}

static bool box_in_shape(const look_box_t *b)
{
    return in_shape(b->x, b->y) && in_shape(b->x + b->w, b->y) && in_shape(b->x, b->y + b->h) &&
           in_shape(b->x + b->w, b->y + b->h);
}

static bool boxes_overlap(const look_box_t *a, const look_box_t *b)
{
    return a->x < b->x + b->w && b->x < a->x + a->w && a->y < b->y + b->h && b->y < a->y + a->h;
}

/* disc_meets_box() is true when the circle's disc and the box share a point. */
static bool disc_meets_box(const look_box_t *c, const look_box_t *b)
{
    double r = c->w / 2.0;
    double cx = c->x + r;
    double cy = c->y + r;
    double nx = cx < b->x ? b->x : cx > b->x + b->w ? b->x + b->w : cx;
    double ny = cy < b->y ? b->y : cy > b->y + b->h ? b->y + b->h : cy;
    return (nx - cx) * (nx - cx) + (ny - cy) * (ny - cy) < r * r;
}

static bool is_drawn(const look_box_t *b)
{
    return b != NULL && (b->kind == LOOK_KIND_TEXT || b->kind == LOOK_KIND_ICON || b->kind == LOOK_KIND_BATTERY);
}

static void test_5_shape_and_overlap(void)
{
    for (int screen = 0; screen < LOOK_SCREEN_COUNT; screen++) {
        const look_box_t *circle = look_box((look_screen_t)screen, LOOK_ITEM_CIRCLE);
        if (circle != NULL) {
            double r = circle->w / 2.0;
            double cx = circle->x + r;
            double cy = circle->y + r;
            for (int k = 0; k < 360; k++) {
                double a = k * 3.14159265358979 / 180.0;
                TEST_ASSERT_TRUE(in_shape(cx + r * cos(a), cy + r * sin(a)));
            }
        }
        for (int i = 0; i < LOOK_ITEM_COUNT; i++) {
            const look_box_t *a = look_box((look_screen_t)screen, (look_item_t)i);
            if (!is_drawn(a)) {
                continue;
            }
            TEST_ASSERT_TRUE_MESSAGE(box_in_shape(a), "a box lies outside the screen's shape");
            for (int j = i + 1; j < LOOK_ITEM_COUNT; j++) {
                const look_box_t *b = look_box((look_screen_t)screen, (look_item_t)j);
                if (is_drawn(b)) {
                    TEST_ASSERT_FALSE_MESSAGE(boxes_overlap(a, b), "two boxes overlap");
                }
            }
            if (circle != NULL && i != LOOK_ITEM_CIRCLE_ICON && i != LOOK_ITEM_CIRCLE_WORD) {
                TEST_ASSERT_FALSE_MESSAGE(disc_meets_box(circle, a), "the circle overlaps a box outside it");
            }
        }
    }
}

static bool corner_inside(double x, double y, double cx, double cy, double limit)
{
    return (x - cx) * (x - cx) + (y - cy) * (y - cy) <= limit * limit;
}

static void check_in_circle(const look_box_t *c, double x, double y, double w, double h)
{
    double r = c->w / 2.0;
    double cx = c->x + r;
    double cy = c->y + r;
    double limit = r - 10.0;
    TEST_ASSERT_TRUE(corner_inside(x, y, cx, cy, limit));
    TEST_ASSERT_TRUE(corner_inside(x + w, y, cx, cy, limit));
    TEST_ASSERT_TRUE(corner_inside(x, y + h, cx, cy, limit));
    TEST_ASSERT_TRUE(corner_inside(x + w, y + h, cx, cy, limit));
}

static void test_6_circle(void)
{
    const look_screen_t screens[] = {LOOK_HOME, LOOK_LOGGED};
    for (size_t k = 0; k < 2; k++) {
        const look_box_t *c = look_box(screens[k], LOOK_ITEM_CIRCLE);
        const look_box_t *icon = look_box(screens[k], LOOK_ITEM_CIRCLE_ICON);
        const look_box_t *word = look_box(screens[k], LOOK_ITEM_CIRCLE_WORD);
        TEST_ASSERT_NOT_NULL(c);
        TEST_ASSERT_EQUAL_INT(260, c->w);
        TEST_ASSERT_EQUAL_INT(260, c->h);
        TEST_ASSERT_EQUAL_INT(88, icon->w);
        TEST_ASSERT_EQUAL_INT(88, icon->h);
        TEST_ASSERT_EQUAL_INT(40, word->size);
        check_in_circle(c, icon->x, icon->y, icon->w, icon->h);
        check_in_circle(c, word->x, word->y, word->w, word->h);
        for (int s = 0; s < 5; s++) {
            int w = look_text_width(look_state((face_state_t)s)->word, 40);
            TEST_ASSERT_TRUE(w > 0 && w <= word->w);
        }
        TEST_ASSERT_TRUE(look_text_width(look_logged()->word, 40) <= word->w);
    }
}

static void test_7_tap_boxes(void)
{
    const look_box_t *home = look_tap_box(LOOK_HOME);
    const look_box_t *med = look_tap_box(LOOK_MEDICATION);
    TEST_ASSERT_NOT_NULL(home);
    TEST_ASSERT_NOT_NULL(med);
    TEST_ASSERT_EQUAL_INT(0, home->x);
    TEST_ASSERT_EQUAL_INT(0, home->y);
    TEST_ASSERT_EQUAL_INT(410, home->w);
    TEST_ASSERT_EQUAL_INT(502, home->h);
    TEST_ASSERT_EQUAL_INT(0, med->x);
    TEST_ASSERT_EQUAL_INT(251, med->y);
    TEST_ASSERT_EQUAL_INT(410, med->w);
    TEST_ASSERT_EQUAL_INT(251, med->h);
    TEST_ASSERT_NULL(look_tap_box(LOOK_LOGGED));
    TEST_ASSERT_NULL(look_tap_box(LOOK_SESSION));
    TEST_ASSERT_NULL(look_tap_box(LOOK_STATUS));
    TEST_ASSERT_TRUE(home->w * home->h >= 68595);
    TEST_ASSERT_TRUE(med->w * med->h >= 68595);
}

static void test_8_characters(void)
{
    const char *chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-./+,:%";
    for (const char *p = chars; *p != '\0'; p++) {
        char one[2] = {*p, '\0'};
        TEST_ASSERT_TRUE(look_text_width(one, 28) > 0);
        TEST_ASSERT_TRUE(look_text_width(one, 40) > 0);
    }
    for (const char *p = "0123456789:-"; *p != '\0'; p++) {
        char one[2] = {*p, '\0'};
        TEST_ASSERT_TRUE(look_text_width(one, 96) > 0);
    }
    TEST_ASSERT_EQUAL_INT(-1, look_text_width("A", 96));
    TEST_ASSERT_EQUAL_INT(-1, look_text_width("x", 30));
}

static void test_9_width_sum(void)
{
    TEST_ASSERT_EQUAL_INT(0, look_text_width("", 28));
    const char *text = "Levodopa, 16:00";
    int sum = 0;
    for (const char *p = text; *p != '\0'; p++) {
        sum += face_adv_40[(unsigned char)*p - FACE_FIRST_CHAR];
    }
    TEST_ASSERT_EQUAL_INT(15, (int)strlen(text));
    TEST_ASSERT_EQUAL_INT(sum, look_text_width(text, 40));
}

static void test_10_fit(void)
{
    int value_w = look_box(LOOK_MEDICATION, LOOK_ITEM_DOSE_VALUE_1)->w;
    TEST_ASSERT_EQUAL_INT(value_w, look_box(LOOK_MEDICATION, LOOK_ITEM_DOSE_VALUE_2)->w);
    TEST_ASSERT_EQUAL_INT(40, look_fit_size("Levodopa, 16:00", value_w, 40, 28));
    int share_w = look_box(LOOK_SESSION, LOOK_ITEM_SHARE)->w;
    TEST_ASSERT_EQUAL_INT(56, look_fit_size("Tremor 12%", share_w, 56, 40));
    int size = look_fit_size("Tremor 100%", share_w, 56, 40);
    TEST_ASSERT_TRUE(size == 56 || size == 40);
    TEST_ASSERT_TRUE(look_text_width("Tremor 100%", size) <= share_w);
}

static void test_11_cut(void)
{
    int value_w = look_box(LOOK_MEDICATION, LOOK_ITEM_DOSE_VALUE_1)->w;
    const char *text = "WWWWWWWWWWWWWWWWWWWW, 16:00";
    char out[64];
    size_t n = look_cut(text, 0, 20, value_w, 28, out, sizeof out);
    TEST_ASSERT_TRUE(n > 0);
    TEST_ASSERT_EQUAL_size_t(strlen(out), n);
    const char *end = "..., 16:00";
    TEST_ASSERT_TRUE(n >= strlen(end));
    TEST_ASSERT_EQUAL_STRING(end, out + n - strlen(end));
    TEST_ASSERT_TRUE(look_text_width(out, 28) <= value_w);
    char more[64];
    size_t ws = n - strlen(end);
    memset(more, 'W', ws + 1);
    strcpy(more + ws + 1, end);
    TEST_ASSERT_TRUE(look_text_width(more, 28) > value_w);
    n = look_cut("Levodopa, 16:00", 0, 8, value_w, 28, out, sizeof out);
    TEST_ASSERT_EQUAL_STRING("Levodopa, 16:00", out);
    TEST_ASSERT_EQUAL_size_t(15, n);
}

static void test_12_longest_texts(void)
{
    static const char *const LONGEST[LOOK_STATUS_ROWS] = {
        "100%", "4.2 V", "999 h 59 m", "150.000 Hz", "4294967295", "999.9 ms", "Off", "11", "ffffffff",
    };
    static const char *const LABELS[LOOK_STATUS_ROWS] = {
        "Battery", "Voltage", "Uptime", "Rate", "Stretch", "Detector", "Recording", "Firmware", "Tables",
    };
    for (int i = 0; i < LOOK_STATUS_ROWS; i++) {
        const look_box_t *row = look_box(LOOK_STATUS, (look_item_t)(LOOK_ITEM_STATUS_1 + i));
        TEST_ASSERT_NOT_NULL(row);
        TEST_ASSERT_EQUAL_INT(28, row->size);
        TEST_ASSERT_TRUE(look_text_width(LABELS[i], 28) + 16 + look_text_width(LONGEST[i], 28) <= row->w);
    }
    int line_w = look_box(LOOK_HOME, LOOK_ITEM_LINE)->w;
    TEST_ASSERT_TRUE(look_text_width("Last tremor 23:59", 28) <= line_w);
    TEST_ASSERT_TRUE(look_text_width("Last tremor none", 28) <= line_w);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_1_contrast);
    RUN_TEST(test_2_distance);
    RUN_TEST(test_3_states);
    RUN_TEST(test_4_text_sizes);
    RUN_TEST(test_5_shape_and_overlap);
    RUN_TEST(test_6_circle);
    RUN_TEST(test_7_tap_boxes);
    RUN_TEST(test_8_characters);
    RUN_TEST(test_9_width_sum);
    RUN_TEST(test_10_fit);
    RUN_TEST(test_11_cut);
    RUN_TEST(test_12_longest_texts);
    return UNITY_END();
}
