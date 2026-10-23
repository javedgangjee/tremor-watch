/*
 * usb_task.c owns the USB port, which is the chip's USB Serial/JTAG port. It
 * is the only file in firmware/main that writes to the port, and no task
 * writes to stdout. ESP-IDF's log goes to UART0 only, so the port carries the
 * recording and the diagnostic lines alone.
 *
 * The task writes the B line first and then START. It takes a copy of each
 * burst part from the record queue and writes the S, T, and R lines. It writes
 * the lines that the other tasks put on the line queue with usb_send(). The
 * other tasks never wait on the line queue, and they count the lines they
 * drop.
 *
 * The task places each line into the driver's send buffer with no wait. The
 * driver takes a whole line or none of it. A line that does not fit, because
 * no program reads the port, is dropped and counted, and the port counts as
 * broken. The next line then first brings the B line and the latest S line
 * again, so a reader that starts late still learns the boot and the stretch.
 *
 * The task also reads the laptop's commands. It answers a bad command itself
 * and sends a good one to the state task, which applies it and answers it.
 * core/recording_format.md describes the lines and the commands.
 */

#include <inttypes.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "driver/usb_serial_jtag.h"
#include "esp_err.h"
#include "esp_random.h"
#include "esp_rom_sys.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "imu_units.h"
#include "reading_time.h"
#include "record.h"
#include "tasks.h"

/* The driver's buffer sizes in bytes. */
#define SEND_BUFFER 4096
#define RECEIVE_BUFFER 512
/* The task waits this long for a record part before it serves the other work. */
#define RECORD_WAIT_MS 10
/* The task reads at most this many received bytes at a time. */
#define READ_CHUNK 64

typedef struct {
    uint32_t port_drops;
    uint32_t restarts;
    uint64_t bytes;
    uint32_t commands;
    uint32_t bad_commands;
} usb_counts_t;

atomic_uint g_line_drops;

static usb_counts_t s_counts;
static record_msg_t s_record;
static line_t s_queued;
/* The text of the kept B and S lines. */
static char s_boot_line[REC_LINE_MAX];
static char s_stretch_line[REC_LINE_MAX];
static bool s_have_stretch;
/* The kept stretch number, first reading, and t0 of the latest S line. */
static uint32_t s_stretch;
static uint64_t s_first;
static int64_t s_t0_us;
/* s_broken is true after a line did not fit, until the B and S lines fit again. */
static bool s_broken;
/* A buffer for one line and its newline. */
static char s_out[LINE_CHARS + 2];
/* The command line so far. It holds REC_COMMAND_MAX characters and a carriage
 * return. s_too_long is true while the task skips a line that is too long. */
static char s_command[REC_COMMAND_MAX + 2];
static size_t s_command_len;
static bool s_too_long;

bool usb_send(const char *fmt, ...)
{
    line_t line;
    va_list args;
    va_start(args, fmt);
    vsnprintf(line.text, sizeof line.text, fmt, args);
    va_end(args);
    if (xQueueSend(g_line_queue, &line, 0) != pdTRUE) {
        atomic_fetch_add(&g_line_drops, 1u);
        return false;
    }
    return true;
}

void send_task_line(const char *name)
{
    usb_send("TASK name=%s core=%d priority=%u", name, (int)xPortGetCoreID(), (unsigned)uxTaskPriorityGet(NULL));
}

/* put_line() places one line and its newline into the driver's send buffer with
 * no wait. It returns false when the line did not fit. */
static bool put_line(const char *text)
{
    size_t len = strnlen(text, LINE_CHARS);
    memcpy(s_out, text, len);
    s_out[len] = '\n';
    int taken = usb_serial_jtag_write_bytes(s_out, len + 1, 0);
    if (taken <= 0) {
        return false;
    }
    s_counts.bytes += (uint64_t)taken;
    return true;
}

/* write_line() writes one line. While the port is broken, the kept B line and
 * the kept S line go first, and the port is whole again when all of them fit.
 * A line that does not fit counts as a port drop. */
static void write_line(const char *text)
{
    if (s_broken) {
        if (!put_line(s_boot_line) || (s_have_stretch && !put_line(s_stretch_line))) {
            s_counts.port_drops++;
            return;
        }
        s_broken = false;
        s_counts.restarts++;
        /* The kept lines have just gone out, so a kept line is not written twice. */
        if (text == s_stretch_line || text == s_boot_line) {
            return;
        }
    }
    if (!put_line(text)) {
        s_counts.port_drops++;
        s_broken = true;
    }
}

/* write_stretch() writes and keeps the S line of the kept stretch with a rate. */
static void write_stretch(uint32_t rate_uhz)
{
    if (rec_stretch(s_stretch_line, sizeof s_stretch_line, s_stretch, s_first, s_t0_us, rate_uhz,
            IMU_GYRO_RANGE_DPS) == 0) {
        return;
    }
    s_have_stretch = true;
    write_line(s_stretch_line);
}

/* take_record() writes the S, T, and R lines of one burst part. */
static void take_record(const record_msg_t *m)
{
    char line[REC_LINE_MAX];
    if ((m->flags & RT_NEW_STRETCH) != 0) {
        s_stretch = m->stretch;
        s_first = m->first_reading;
        s_t0_us = m->stamp_us;
        write_stretch(m->rate_uhz);
    } else if ((m->flags & RT_RATE_SET) != 0) {
        write_stretch(m->rate_uhz);
    }
    if (m->first_part && rec_burst(line, sizeof line, m->first_reading, m->burst_count, m->stamp_us) > 0) {
        write_line(line);
    }
    for (uint32_t i = 0; i < m->count; i++) {
        /* Axes 3 to 5 are the gyroscope, and axes 0 to 2 are the accelerometer. */
        if (rec_reading(line, sizeof line, m->first_reading + i, &m->raw[i][3], &m->raw[i][0]) > 0) {
            write_line(line);
        }
    }
}

/* answer() writes the A line of a command that the task answers itself. */
static void answer(rec_cmd_t command, rec_result_t result)
{
    char line[REC_LINE_MAX];
    s_counts.bad_commands++;
    if (rec_reply(line, sizeof line, command, result) > 0) {
        write_line(line);
    }
}

/* take_command() handles one command line, whose newline arrived at stamp_us. */
static void take_command(int64_t stamp_us)
{
    if (s_too_long) {
        s_counts.commands++;
        answer(REC_CMD_UNKNOWN, REC_BAD_FORMAT);
        return;
    }
    s_command[s_command_len] = '\0';
    state_msg_t msg;
    memset(&msg, 0, sizeof msg);
    rec_result_t result = rec_parse_command(s_command, &msg.command);
    if (msg.command.kind == REC_CMD_EMPTY) {
        return;
    }
    s_counts.commands++;
    if (result != REC_DONE) {
        answer(msg.command.kind, result);
        return;
    }
    msg.kind = STATE_MSG_COMMAND;
    msg.at_us = stamp_us;
    if (xQueueSend(g_state_queue, &msg, 0) != pdTRUE) {
        answer(msg.command.kind, REC_BUSY);
    }
}

/* read_commands() reads the received bytes with no wait and handles each
 * command line at its newline. */
static void read_commands(void)
{
    uint8_t chunk[READ_CHUNK];
    for (;;) {
        int got = usb_serial_jtag_read_bytes(chunk, sizeof chunk, 0);
        if (got <= 0) {
            return;
        }
        for (int i = 0; i < got; i++) {
            char ch = (char)chunk[i];
            if (ch == '\n') {
                take_command(esp_timer_get_time());
                s_command_len = 0;
                s_too_long = false;
            } else if (s_too_long) {
                continue;
            } else if (s_command_len < sizeof s_command - 1) {
                s_command[s_command_len++] = ch;
            } else {
                s_too_long = true;
            }
        }
    }
}

static void write_minute_line(uint32_t minute)
{
    char line[LINE_CHARS + 1];
    snprintf(line, sizeof line,
             "USB_MINUTE minute=%" PRIu32 " line_drops=%u port_drops=%" PRIu32 " restarts=%" PRIu32 " bytes=%" PRIu64
             " commands=%" PRIu32 " bad_commands=%" PRIu32 " stack_free=%u",
             minute, atomic_load(&g_line_drops), s_counts.port_drops, s_counts.restarts, s_counts.bytes,
             s_counts.commands, s_counts.bad_commands, (unsigned)uxTaskGetStackHighWaterMark(NULL));
    write_line(line);
}

void usb_task(void *arg)
{
    (void)arg;
    /* The ROM's own print function also writes to this port, and ESP-IDF's
     * early log and its log from interrupts use it. Removing its second
     * channel keeps that text on UART0 only, so it never breaks a line of
     * the recording. */
    esp_rom_install_channel_putc(2, NULL);
    usb_serial_jtag_driver_config_t config = {
        .tx_buffer_size = SEND_BUFFER,
        .rx_buffer_size = RECEIVE_BUFFER,
    };
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&config));

    rec_boot(s_boot_line, sizeof s_boot_line, esp_random(), (uint32_t)esp_reset_reason(), FIRMWARE_VERSION,
             TABLE_HASH);
    write_line(s_boot_line);
    char line[REC_LINE_MAX];
    snprintf(line, sizeof line, "START uptime_us=%" PRId64, esp_timer_get_time());
    write_line(line);
    send_task_line("usb");

    uint32_t minute = 1;
    for (;;) {
        if (xQueueReceive(g_record_queue, &s_record, pdMS_TO_TICKS(RECORD_WAIT_MS)) == pdTRUE) {
            take_record(&s_record);
        }
        while (xQueueReceive(g_line_queue, &s_queued, 0) == pdTRUE) {
            write_line(s_queued.text);
        }
        read_commands();
        if (esp_timer_get_time() >= (int64_t)minute * MINUTE_US) {
            write_minute_line(minute);
            minute++;
        }
    }
}
