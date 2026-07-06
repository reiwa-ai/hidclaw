/*
 * Copyright (c) 2024 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <sample_usbd.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/uart.h>

#include <zephyr/usb/usbd.h>
#include <zephyr/usb/class/usbd_hid.h>

#include <zephyr/logging/log.h>
#include <stdlib.h>
#include <string.h>
LOG_MODULE_REGISTER(main, LOG_LEVEL_INF);

#define UART_LINE_MAX 262
#define TEXT_PREFIX "TEXT "
#define TEXT_MAX_LENGTH 256
#define MOUSE_MOVE_PREFIX "MOUSE_MOVE "
#define MOUSE_MOVE_MAX 100
#define KEY_PRESS_MS 20
#define MODIFIER_ONLY_KEY_PRESS_MS 120
#define ACK_OK "PICO_HID_OK\n"
#define ACK_ERR "PICO_HID_ERR\n"

#define HID_JIS_KEYBOARD_REPORT_DESC() {				\
	HID_USAGE_PAGE(HID_USAGE_GEN_DESKTOP),				\
	HID_USAGE(HID_USAGE_GEN_DESKTOP_KEYBOARD),			\
	HID_COLLECTION(HID_COLLECTION_APPLICATION),			\
		HID_USAGE_PAGE(HID_USAGE_GEN_DESKTOP_KEYPAD),		\
		HID_USAGE_MIN8(0xE0),					\
		HID_USAGE_MAX8(0xE7),					\
		HID_LOGICAL_MIN8(0),					\
		HID_LOGICAL_MAX8(1),					\
		HID_REPORT_SIZE(1),					\
		HID_REPORT_COUNT(8),					\
		HID_INPUT(0x02),					\
		HID_REPORT_SIZE(8),					\
		HID_REPORT_COUNT(1),					\
		HID_INPUT(0x03),					\
		HID_REPORT_SIZE(1),					\
		HID_REPORT_COUNT(5),					\
		HID_USAGE_PAGE(HID_USAGE_GEN_LEDS),			\
		HID_USAGE_MIN8(1),					\
		HID_USAGE_MAX8(5),					\
		HID_OUTPUT(0x02),					\
		HID_REPORT_SIZE(3),					\
		HID_REPORT_COUNT(1),					\
		HID_OUTPUT(0x03),					\
		HID_REPORT_SIZE(8),					\
		HID_REPORT_COUNT(6),					\
		HID_LOGICAL_MIN8(0),					\
		HID_LOGICAL_MAX16(0x89, 0x00),				\
		HID_USAGE_PAGE(HID_USAGE_GEN_DESKTOP_KEYPAD),		\
		HID_USAGE_MIN8(0),					\
		HID_USAGE_MAX16(0x89, 0x00),				\
		HID_INPUT(0x00),					\
	HID_END_COLLECTION,						\
}

static const uint8_t kb_report_desc[] = HID_JIS_KEYBOARD_REPORT_DESC();
static const uint8_t mouse_report_desc[] = HID_MOUSE_REPORT_DESC(2);

enum kb_leds_idx {
	KB_LED_NUMLOCK = 0,
	KB_LED_CAPSLOCK,
	KB_LED_SCROLLLOCK,
	KB_LED_COUNT,
};

static const struct gpio_dt_spec kb_leds[KB_LED_COUNT] = {
	GPIO_DT_SPEC_GET_OR(DT_ALIAS(led0), gpios, {0}),
	GPIO_DT_SPEC_GET_OR(DT_ALIAS(led1), gpios, {0}),
	GPIO_DT_SPEC_GET_OR(DT_ALIAS(led2), gpios, {0}),
};

enum kb_report_idx {
	KB_MOD_KEY = 0,
	KB_RESERVED,
	KB_KEY_CODE1,
	KB_KEY_CODE2,
	KB_KEY_CODE3,
	KB_KEY_CODE4,
	KB_KEY_CODE5,
	KB_KEY_CODE6,
	KB_REPORT_COUNT,
};

enum mouse_report_idx {
	MOUSE_BTN_REPORT_IDX = 0,
	MOUSE_X_REPORT_IDX,
	MOUSE_Y_REPORT_IDX,
	MOUSE_WHEEL_REPORT_IDX,
	MOUSE_REPORT_COUNT,
};

#define MOUSE_BTN_LEFT BIT(0)
#define MOUSE_BTN_RIGHT BIT(1)

struct hid_key {
	uint8_t modifier;
	uint8_t key;
};

#define HID_KEY_JIS_RO 0x87U
#define HID_KEY_JIS_YEN 0x89U

UDC_STATIC_BUF_DEFINE(kb_report, KB_REPORT_COUNT);
UDC_STATIC_BUF_DEFINE(mouse_report, MOUSE_REPORT_COUNT);
static uint32_t kb_duration;
static bool kb_ready;
static bool mouse_ready;

static void kb_iface_ready(const struct device *dev, const bool ready)
{
	LOG_INF("HID device %s interface is %s",
		dev->name, ready ? "ready" : "not ready");
	kb_ready = ready;
}

static int kb_get_report(const struct device *dev,
			 const uint8_t type, const uint8_t id, const uint16_t len,
			 uint8_t *const buf)
{
	LOG_WRN("Get Report not implemented, Type %u ID %u", type, id);

	return 0;
}

static int kb_verify_set_report(const struct device *dev, const uint8_t type,
				const uint8_t id, const uint16_t len)
{
	if (type != HID_REPORT_TYPE_OUTPUT) {
		LOG_WRN("Unsupported report type");
		return -ENOTSUP;
	}

	if (id != 0) {
		LOG_ERR("Unsupported report id %d", id);
		return -ENOTSUP;
	}

	if (len != 1) {
		LOG_WRN("Unsupported report length %d", len);
		return -ENOTSUP;
	}

	return 0;
}

static int kb_set_report(const struct device *dev,
			 const uint8_t type, const uint8_t id, const uint16_t len,
			 const uint8_t *const buf)
{
	if (type != HID_REPORT_TYPE_OUTPUT) {
		LOG_WRN("Unsupported report type");
		return -ENOTSUP;
	}

	for (unsigned int i = 0; i < ARRAY_SIZE(kb_leds); i++) {
		if (kb_leds[i].port == NULL) {
			continue;
		}

		(void)gpio_pin_set_dt(&kb_leds[i], buf[0] & BIT(i));
	}

	return 0;
}

/* Idle duration is stored but not used to calculate idle reports. */
static void kb_set_idle(const struct device *dev,
			const uint8_t id, const uint32_t duration)
{
	LOG_INF("Set Idle %u to %u", id, duration);
	kb_duration = duration;
}

static uint32_t kb_get_idle(const struct device *dev, const uint8_t id)
{
	LOG_INF("Get Idle %u to %u", id, kb_duration);
	return kb_duration;
}

static void kb_set_protocol(const struct device *dev, const uint8_t proto)
{
	LOG_INF("Protocol changed to %s",
		proto == 0U ? "Boot Protocol" : "Report Protocol");
}

static void kb_output_report(const struct device *dev, const uint16_t len,
			     const uint8_t *const buf)
{
	LOG_HEXDUMP_DBG(buf, len, "o.r.");
	kb_set_report(dev, HID_REPORT_TYPE_OUTPUT, 0U, len, buf);
}

struct hid_device_ops kb_ops = {
	.iface_ready = kb_iface_ready,
	.get_report = kb_get_report,
	.verify_set_report = kb_verify_set_report,
	.set_report = kb_set_report,
	.set_idle = kb_set_idle,
	.get_idle = kb_get_idle,
	.set_protocol = kb_set_protocol,
	.output_report = kb_output_report,
};

static void mouse_iface_ready(const struct device *dev, const bool ready)
{
	LOG_INF("HID device %s interface is %s",
		dev->name, ready ? "ready" : "not ready");
	mouse_ready = ready;
}

static int mouse_get_report(const struct device *dev,
			    const uint8_t type, const uint8_t id, const uint16_t len,
			    uint8_t *const buf)
{
	LOG_WRN("Mouse Get Report not implemented, Type %u ID %u", type, id);

	return 0;
}

struct hid_device_ops mouse_ops = {
	.iface_ready = mouse_iface_ready,
	.get_report = mouse_get_report,
};

/* doc device msg-cb start */
static void msg_cb(struct usbd_context *const usbd_ctx,
		   const struct usbd_msg *const msg)
{
	LOG_INF("USBD message: %s", usbd_msg_type_string(msg->type));

	if (msg->type == USBD_MSG_CONFIGURATION) {
		LOG_INF("\tConfiguration value %d", msg->status);
	}

	if (usbd_can_detect_vbus(usbd_ctx)) {
		if (msg->type == USBD_MSG_VBUS_READY) {
			if (usbd_enable(usbd_ctx)) {
				LOG_ERR("Failed to enable device support");
			}
		}

		if (msg->type == USBD_MSG_VBUS_REMOVED) {
			if (usbd_disable(usbd_ctx)) {
				LOG_ERR("Failed to disable device support");
			}
		}
	}
}
/* doc device msg-cb end */

static void status_blink_led(void)
{
	static bool on;

	if (kb_leds[0].port == NULL) {
		return;
	}

	on = !on;
	LOG_INF("UART received, LED state=%d", on);
	(void)gpio_pin_set_dt(&kb_leds[0], on);
}

static int hid_send_key(const struct device *hid_dev, struct hid_key hid_key)
{
	int ret;

	if (!kb_ready) {
		LOG_WRN("USB HID device is not ready");
		return -EAGAIN;
	}

	memset(kb_report, 0, sizeof(kb_report));
	kb_report[KB_MOD_KEY] = hid_key.modifier;
	kb_report[KB_KEY_CODE1] = hid_key.key;

	ret = hid_device_submit_report(hid_dev, KB_REPORT_COUNT, kb_report);
	if (ret) {
		LOG_ERR("HID key press error, %d", ret);
		return ret;
	}

	if (hid_key.key == 0U && hid_key.modifier != HID_KBD_MODIFIER_NONE) {
		k_msleep(MODIFIER_ONLY_KEY_PRESS_MS);
	} else {
		k_msleep(KEY_PRESS_MS);
	}

	memset(kb_report, 0, sizeof(kb_report));

	ret = hid_device_submit_report(hid_dev, KB_REPORT_COUNT, kb_report);
	if (ret) {
		LOG_ERR("HID key release error, %d", ret);
		return ret;
	}

	k_msleep(KEY_PRESS_MS);

	return 0;
}

static bool ascii_to_hid_key(char ch, struct hid_key *hid_key)
{
	hid_key->modifier = HID_KBD_MODIFIER_NONE;

	if (ch >= 'a' && ch <= 'z') {
		hid_key->key = HID_KEY_A + (ch - 'a');
		return true;
	}

	if (ch >= 'A' && ch <= 'Z') {
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_A + (ch - 'A');
		return true;
	}

	if (ch >= '1' && ch <= '9') {
		hid_key->key = HID_KEY_1 + (ch - '1');
		return true;
	}

	switch (ch) {
	case '0':
		hid_key->key = HID_KEY_0;
		return true;
	case ' ':
		hid_key->key = HID_KEY_SPACE;
		return true;
	case '-':
		hid_key->key = HID_KEY_MINUS;
		return true;
	case '=':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_MINUS;
		return true;
	case '[':
		hid_key->key = HID_KEY_RIGHTBRACE;
		return true;
	case ']':
		hid_key->key = HID_KEY_BACKSLASH;
		return true;
	case '\\':
		hid_key->key = HID_KEY_JIS_YEN;
		return true;
	case ';':
		hid_key->key = HID_KEY_SEMICOLON;
		return true;
	case '\'':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_7;
		return true;
	case '`':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_LEFTBRACE;
		return true;
	case ',':
		hid_key->key = HID_KEY_COMMA;
		return true;
	case '.':
		hid_key->key = HID_KEY_DOT;
		return true;
	case '/':
		hid_key->key = HID_KEY_SLASH;
		return true;
	case '!':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_1;
		return true;
	case '@':
		hid_key->key = HID_KEY_LEFTBRACE;
		return true;
	case '#':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_3;
		return true;
	case '$':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_4;
		return true;
	case '%':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_5;
		return true;
	case '^':
		hid_key->key = HID_KEY_EQUAL;
		return true;
	case '&':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_6;
		return true;
	case '*':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_APOSTROPHE;
		return true;
	case '(':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_8;
		return true;
	case ')':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_9;
		return true;
	case '_':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_JIS_RO;
		return true;
	case '+':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_SEMICOLON;
		return true;
	case '{':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_RIGHTBRACE;
		return true;
	case '}':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_BACKSLASH;
		return true;
	case '|':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_JIS_YEN;
		return true;
	case ':':
		hid_key->key = HID_KEY_APOSTROPHE;
		return true;
	case '"':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_2;
		return true;
	case '~':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_EQUAL;
		return true;
	case '<':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_COMMA;
		return true;
	case '>':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_DOT;
		return true;
	case '?':
		hid_key->modifier = HID_KBD_MODIFIER_LEFT_SHIFT;
		hid_key->key = HID_KEY_SLASH;
		return true;
	default:
		return false;
	}
}

static int hid_type_text(const struct device *hid_dev, const char *text)
{
	size_t len = strlen(text);

	if (len > TEXT_MAX_LENGTH) {
		LOG_WRN("TEXT too long; max %d chars", TEXT_MAX_LENGTH);
		return -EINVAL;
	}

	for (size_t i = 0; i < len; i++) {
		struct hid_key hid_key;
		int ret;

		if (!ascii_to_hid_key(text[i], &hid_key)) {
			LOG_WRN("Unsupported TEXT char: 0x%02x", text[i]);
			return -EINVAL;
		}

		ret = hid_send_key(hid_dev, hid_key);
		if (ret) {
			return ret;
		}
	}

	return 0;
}

static int hid_key_command(const struct device *hid_dev, const char *name)
{
	struct hid_key hid_key = {
		.modifier = HID_KBD_MODIFIER_NONE,
		.key = 0U,
	};
	char token[16];
	size_t token_len = 0;
	bool have_key = false;

	for (size_t i = 0; ; i++) {
		char ch = name[i];

		if (ch != '+' && ch != '\0') {
			if (token_len >= (sizeof(token) - 1)) {
				LOG_WRN("KEY token too long: %s", name);
				return -EINVAL;
			}

			token[token_len++] = ch;
			continue;
		}

		if (token_len == 0) {
			LOG_WRN("Empty KEY token: %s", name);
			return -EINVAL;
		}

		token[token_len] = '\0';
		token_len = 0;

		if (strcmp(token, "CTRL") == 0 || strcmp(token, "CONTROL") == 0) {
			hid_key.modifier |= HID_KBD_MODIFIER_LEFT_CTRL;
		} else if (strcmp(token, "SHIFT") == 0) {
			hid_key.modifier |= HID_KBD_MODIFIER_LEFT_SHIFT;
		} else if (strcmp(token, "ALT") == 0) {
			hid_key.modifier |= HID_KBD_MODIFIER_LEFT_ALT;
		} else if (strcmp(token, "WIN") == 0 || strcmp(token, "GUI") == 0 ||
			   strcmp(token, "META") == 0 || strcmp(token, "CMD") == 0) {
			hid_key.modifier |= HID_KBD_MODIFIER_LEFT_UI;
		} else {
			uint8_t key;

			if (have_key) {
				LOG_WRN("KEY supports one non-modifier key: %s", name);
				return -EINVAL;
			}

			if (strlen(token) == 1 && token[0] >= 'A' && token[0] <= 'Z') {
				key = HID_KEY_A + (token[0] - 'A');
			} else if (strlen(token) == 1 && token[0] >= '1' && token[0] <= '9') {
				key = HID_KEY_1 + (token[0] - '1');
			} else if (strcmp(token, "0") == 0) {
				key = HID_KEY_0;
			} else if (strcmp(token, "ENTER") == 0 || strcmp(token, "RETURN") == 0) {
				key = HID_KEY_ENTER;
			} else if (strcmp(token, "ESC") == 0 || strcmp(token, "ESCAPE") == 0) {
				key = HID_KEY_ESC;
			} else if (strcmp(token, "BACKSPACE") == 0) {
				key = HID_KEY_BACKSPACE;
			} else if (strcmp(token, "TAB") == 0) {
				key = HID_KEY_TAB;
			} else if (strcmp(token, "SPACE") == 0) {
				key = HID_KEY_SPACE;
			} else if (strcmp(token, "DELETE") == 0 || strcmp(token, "DEL") == 0) {
				key = HID_KEY_DELETE;
			} else if (strcmp(token, "F1") == 0) {
				key = HID_KEY_F1;
			} else if (strcmp(token, "F2") == 0) {
				key = HID_KEY_F2;
			} else if (strcmp(token, "F3") == 0) {
				key = HID_KEY_F3;
			} else if (strcmp(token, "F4") == 0) {
				key = HID_KEY_F4;
			} else if (strcmp(token, "F5") == 0) {
				key = HID_KEY_F5;
			} else if (strcmp(token, "F6") == 0) {
				key = HID_KEY_F6;
			} else if (strcmp(token, "F7") == 0) {
				key = HID_KEY_F7;
			} else if (strcmp(token, "F8") == 0) {
				key = HID_KEY_F8;
			} else if (strcmp(token, "F9") == 0) {
				key = HID_KEY_F9;
			} else if (strcmp(token, "F10") == 0) {
				key = HID_KEY_F10;
			} else if (strcmp(token, "F11") == 0) {
				key = HID_KEY_F11;
			} else if (strcmp(token, "F12") == 0) {
				key = HID_KEY_F12;
			} else {
				LOG_WRN("Unknown KEY token: %s", token);
				return -EINVAL;
			}

			hid_key.key = key;
			have_key = true;
		}

		if (ch == '\0') {
			break;
		}
	}

	if (!have_key && hid_key.modifier == HID_KBD_MODIFIER_NONE) {
		LOG_WRN("KEY has no non-modifier key: %s", name);
		return -EINVAL;
	}

	return hid_send_key(hid_dev, hid_key);
}

static int mouse_submit_report(const struct device *mouse_dev, uint8_t buttons,
			       int8_t x, int8_t y)
{
	int ret;

	if (!mouse_ready) {
		LOG_WRN("USB HID mouse is not ready");
		return -EAGAIN;
	}

	memset(mouse_report, 0, sizeof(mouse_report));
	mouse_report[MOUSE_BTN_REPORT_IDX] = buttons;
	mouse_report[MOUSE_X_REPORT_IDX] = (uint8_t)x;
	mouse_report[MOUSE_Y_REPORT_IDX] = (uint8_t)y;

	ret = hid_device_submit_report(mouse_dev, MOUSE_REPORT_COUNT, mouse_report);
	if (ret) {
		LOG_ERR("Mouse HID submit report error, %d", ret);
		return ret;
	}

	k_msleep(20);

	return 0;
}

static int mouse_move_command(const struct device *mouse_dev, const char *args)
{
	char *endptr;
	long x;
	long y;

	x = strtol(args, &endptr, 10);
	if (endptr == args || *endptr != ' ') {
		LOG_WRN("Invalid MOUSE_MOVE x value: %s", args);
		return -EINVAL;
	}

	while (*endptr == ' ') {
		endptr++;
	}

	args = endptr;
	y = strtol(args, &endptr, 10);
	if (endptr == args || *endptr != '\0') {
		LOG_WRN("Invalid MOUSE_MOVE y value: %s", args);
		return -EINVAL;
	}

	if (x < -MOUSE_MOVE_MAX || x > MOUSE_MOVE_MAX ||
	    y < -MOUSE_MOVE_MAX || y > MOUSE_MOVE_MAX) {
		LOG_WRN("MOUSE_MOVE out of range: %ld %ld", x, y);
		return -EINVAL;
	}

	return mouse_submit_report(mouse_dev, 0U, (int8_t)x, (int8_t)y);
}

static int mouse_click_command(const struct device *mouse_dev, const char *button)
{
	uint8_t buttons;
	int ret;

	if (strcmp(button, "LEFT") == 0) {
		buttons = MOUSE_BTN_LEFT;
	} else if (strcmp(button, "RIGHT") == 0) {
		buttons = MOUSE_BTN_RIGHT;
	} else {
		LOG_WRN("Unknown CLICK button: %s", button);
		return -EINVAL;
	}

	ret = mouse_submit_report(mouse_dev, buttons, 0, 0);
	if (ret) {
		return ret;
	}

	return mouse_submit_report(mouse_dev, 0U, 0, 0);
}

static void uart_send_text(const struct device *uart_dev, const char *text)
{
	for (size_t i = 0; text[i] != '\0'; i++) {
		uart_poll_out(uart_dev, text[i]);
	}
}

static void handle_uart_line(const struct device *kb_dev, const struct device *mouse_dev,
			     const struct device *uart_dev, const char *line)
{
	int ret;

	LOG_INF("UART line: %s", line);

	if (strncmp(line, TEXT_PREFIX, strlen(TEXT_PREFIX)) == 0) {
		ret = hid_type_text(kb_dev, line + strlen(TEXT_PREFIX));
	} else if (strcmp(line, "PING") == 0) {
		ret = 0;
	} else if (strncmp(line, "KEY ", 4) == 0) {
		ret = hid_key_command(kb_dev, line + 4);
	} else if (strncmp(line, MOUSE_MOVE_PREFIX, strlen(MOUSE_MOVE_PREFIX)) == 0) {
		ret = mouse_move_command(mouse_dev, line + strlen(MOUSE_MOVE_PREFIX));
	} else if (strncmp(line, "CLICK ", 6) == 0) {
		ret = mouse_click_command(mouse_dev, line + 6);
	} else {
		LOG_WRN("Unknown command: %s", line);
		uart_send_text(uart_dev, ACK_ERR);
		return;
	}

	if (ret == 0) {
		status_blink_led();
		uart_send_text(uart_dev, ACK_OK);
	} else {
		uart_send_text(uart_dev, ACK_ERR);
	}
}

static void uart_handle_char(const struct device *kb_dev, const struct device *mouse_dev,
			     const struct device *uart_dev, char ch, char *line, size_t *line_len,
			     bool *dropping_line)
{
	if (ch == '\r') {
		return;
	}

	if (ch == '\n') {
		if (*dropping_line) {
			*dropping_line = false;
			*line_len = 0;
			return;
		}

		if (*line_len > 0) {
			line[*line_len] = '\0';
			handle_uart_line(kb_dev, mouse_dev, uart_dev, line);
			*line_len = 0;
		}

		return;
	}

	if (*dropping_line) {
		return;
	}

	if (*line_len >= (UART_LINE_MAX - 1)) {
		LOG_WRN("UART line too long; dropping until newline");
		*dropping_line = true;
		*line_len = 0;
		return;
	}

	line[*line_len] = ch;
	(*line_len)++;
}

int main(void)
{
	struct usbd_context *sample_usbd;
	const struct device *kb_dev = DEVICE_DT_GET(DT_NODELABEL(hid_keyboard));
	const struct device *mouse_dev = DEVICE_DT_GET(DT_NODELABEL(hid_mouse));
	const struct device *uart_dev = DEVICE_DT_GET(DT_CHOSEN(zephyr_console));
	char uart_line[UART_LINE_MAX];
	size_t uart_line_len = 0;
	bool dropping_line = false;
	int ret;

	for (unsigned int i = 0; i < ARRAY_SIZE(kb_leds); i++) {
		if (kb_leds[i].port == NULL) {
			continue;
		}

		if (!gpio_is_ready_dt(&kb_leds[i])) {
			LOG_ERR("LED device %s is not ready", kb_leds[i].port->name);
			return -EIO;
		}

		ret = gpio_pin_configure_dt(&kb_leds[i], GPIO_OUTPUT_INACTIVE);
		if (ret != 0) {
			LOG_ERR("Failed to configure the LED pin, %d", ret);
			return -EIO;
		}
	}

	if (!device_is_ready(kb_dev)) {
		LOG_ERR("Keyboard HID Device is not ready");
		return -EIO;
	}

	if (!device_is_ready(mouse_dev)) {
		LOG_ERR("Mouse HID Device is not ready");
		return -EIO;
	}

	if (!device_is_ready(uart_dev)) {
		LOG_ERR("UART device is not ready");
		return -EIO;
	}

	ret = hid_device_register(kb_dev,
				  kb_report_desc, sizeof(kb_report_desc),
				  &kb_ops);
	if (ret != 0) {
		LOG_ERR("Failed to register keyboard HID Device, %d", ret);
		return ret;
	}

	ret = hid_device_register(mouse_dev,
				  mouse_report_desc, sizeof(mouse_report_desc),
				  &mouse_ops);
	if (ret != 0) {
		LOG_ERR("Failed to register mouse HID Device, %d", ret);
		return ret;
	}

	if (IS_ENABLED(CONFIG_USBD_HID_SET_POLLING_PERIOD)) {
		ret = hid_device_set_in_polling(kb_dev, 1000);
		if (ret) {
			LOG_WRN("Failed to set keyboard IN report polling period, %d", ret);
		}

		ret = hid_device_set_in_polling(mouse_dev, 1000);
		if (ret) {
			LOG_WRN("Failed to set mouse IN report polling period, %d", ret);
		}

		ret = hid_device_set_out_polling(kb_dev, 1000);
		if (ret != 0 && ret != -ENOTSUP) {
			LOG_WRN("Failed to set keyboard OUT report polling period, %d", ret);
		}
	}

	sample_usbd = sample_usbd_init_device(msg_cb);
	if (sample_usbd == NULL) {
		LOG_ERR("Failed to initialize USB device");
		return -ENODEV;
	}

	if (!usbd_can_detect_vbus(sample_usbd)) {
		/* doc device enable start */
		ret = usbd_enable(sample_usbd);
		if (ret) {
			LOG_ERR("Failed to enable device support");
			return ret;
		}
		/* doc device enable end */
	}

	LOG_INF("HID keyboard and mouse are initialized");
	LOG_INF("Step 6 UART to HID keyboard/mouse is ready");

	while (true) {
		unsigned char ch;

		while (uart_poll_in(uart_dev, &ch) == 0) {
			uart_handle_char(kb_dev, mouse_dev, uart_dev, (char)ch, uart_line,
					 &uart_line_len, &dropping_line);
		}

		k_sleep(K_MSEC(10));
	}

	return 0;
}
