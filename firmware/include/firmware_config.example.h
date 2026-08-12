#pragma once

// Copy this file to firmware_config.h in the same directory. The real file is
// ignored by Git. Never commit actual Wi-Fi credentials or private CA material.

#define AIRMONITOR_WIFI_SSID "YOUR_WIFI_NAME"
#define AIRMONITOR_WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// Browser/host loopback addresses do not work from an ESP32. For local LAN
// testing use the computer's Wi-Fi or hotspot address, for example:
// http://192.168.1.100:8000
#define AIRMONITOR_API_BASE_URL "http://192.168.1.100:8000"

// Numeric ID returned by POST /api/v1/devices and the matching stable UID.
#define AIRMONITOR_DEVICE_ID 1U
#define AIRMONITOR_DEVICE_UID "airmonitor-device-001"

// Required for an https:// API URL. Keep empty for local http:// development.
// Production example: "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n"
#define AIRMONITOR_API_CA_CERT ""

#define AIRMONITOR_MEASUREMENT_INTERVAL_MS 5000U
#define AIRMONITOR_SESSION_POLL_INTERVAL_MS 5000U
#define AIRMONITOR_HTTP_TIMEOUT_MS 3000U
#define AIRMONITOR_PENDING_QUEUE_CAPACITY 24U

// Replace the first value with a LAN NTP server when the hotspot has no
// internet access. Firmware never fabricates a timestamp.
#define AIRMONITOR_NTP_SERVER_1 "pool.ntp.org"
#define AIRMONITOR_NTP_SERVER_2 "time.google.com"
#define AIRMONITOR_NTP_SERVER_3 "time.cloudflare.com"
