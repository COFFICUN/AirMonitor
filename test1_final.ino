#include <M5Stack.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Adafruit_SHT31.h>
#include <Plantower_PMS7003.h>
#include <math.h>
#include <time.h>
#include "secrets.h"

const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;
const char* serverURL = "https://172.20.10.4:5000/update";
const char* deviceUid = "airmonitor-main";

static const int PMS_RX_PIN = 16;
static const int PMS_TX_PIN = 17;

const unsigned long WIFI_RETRY_INTERVAL_MS   = 10000;
const unsigned long SENSOR_READ_INTERVAL_MS  = 2000;
const unsigned long UI_REFRESH_MS            = 800;
const unsigned long SEND_INTERVAL_MS         = 5000;
const unsigned long PMS_TIMEOUT_MS           = 15000;
const unsigned long NTP_RETRY_INTERVAL_MS    = 30000;

const int PM_FILTER_SIZE = 5;

Plantower_PMS7003 pms;
Adafruit_SHT31 sht31 = Adafruit_SHT31();

struct SensorData {
  float temperature = NAN;
  float humidity = NAN;

  int pm1 = 0;
  int pm25 = 0;
  int pm10 = 0;

  int pc03 = 0;
  int pc05 = 0;
  int pc10 = 0;
  int pc25 = 0;
  int pc50 = 0;
  int pc100 = 0;

  bool shtOk = false;
  bool pmsOk = false;
  bool hasValidData = false;
};

SensorData currentData;

unsigned long lastWiFiCheck = 0;
unsigned long lastSensorRead = 0;
unsigned long lastUIRefresh = 0;
unsigned long lastSendTime = 0;
unsigned long lastPmsDataTime = 0;
unsigned long lastSuccessPostTime = 0;
unsigned long lastNtpSyncAttempt = 0;

bool serverEnabled = true;
bool lastPostSuccess = false;
bool sendingNow = false;
bool timeSynced = false;
int lastHttpCode = 0;
int currentScreen = 0; // 0 MAIN, 1 PARTICLES, 2 SYSTEM

String statusMessage = "READY";
unsigned long statusMessageUntil = 0;
String lastServerReason = "WAIT START";

int pm1Buffer[PM_FILTER_SIZE] = {0};
int pm25Buffer[PM_FILTER_SIZE] = {0};
int pm10Buffer[PM_FILTER_SIZE] = {0};
int pmBufferIndex = 0;
int pmBufferCount = 0;

const uint16_t C_BG   = BLACK;
const uint16_t C_TXT  = WHITE;
const uint16_t C_SUB  = LIGHTGREY;

uint16_t cOrange() { return M5.Lcd.color565(255, 165, 0); }
uint16_t cPurple() { return M5.Lcd.color565(180, 80, 255); }
uint16_t cBlue()   { return M5.Lcd.color565(90, 170, 255); }
uint16_t cGreen()  { return M5.Lcd.color565(70, 220, 120); }
uint16_t cYellow() { return M5.Lcd.color565(255, 210, 80); }
uint16_t cRed()    { return M5.Lcd.color565(255, 90, 90); }

uint16_t getAQColor(int pm25) {
  if (pm25 <= 12) return GREEN;
  if (pm25 <= 35) return YELLOW;
  if (pm25 <= 55) return cOrange();
  if (pm25 <= 150) return RED;
  return cPurple();
}

const char* getAirQualityLabel(int pm25) {
  if (pm25 <= 12) return "GOOD";
  if (pm25 <= 35) return "MODERATE";
  if (pm25 <= 55) return "ELEVATED";
  if (pm25 <= 150) return "UNHEALTHY";
  return "HAZARDOUS";
}

String shortAgo(unsigned long lastTimeMs) {
  if (lastTimeMs == 0) return "never";
  unsigned long diffSec = (millis() - lastTimeMs) / 1000;
  if (diffSec < 60) return String(diffSec) + "s";
  return String(diffSec / 60) + "m";
}

String getWiFiStatusText() {
  return WiFi.status() == WL_CONNECTED ? "OK" : "LOST";
}

String getServerStatusText() {
  if (!serverEnabled) return "OFF";
  if (sendingNow) return "SEND";
  if (lastPostSuccess) return "OK";
  if (lastHttpCode == 409) return "WAIT";
  if (lastHttpCode == 0) return "WAIT";
  return "ERR";
}

uint16_t getStatusDotColor() {
  if (!serverEnabled) return cBlue();
  if (WiFi.status() != WL_CONNECTED) return cRed();
  if (sendingNow) return cYellow();
  if (lastHttpCode == 409) return cBlue();
  if (lastPostSuccess) return cGreen();
  return cRed();
}

void setStatusMessage(const String& msg, unsigned long durationMs = 1500) {
  statusMessage = msg;
  statusMessageUntil = millis() + durationMs;
}

void addPMToBuffer(int pm1, int pm25, int pm10) {
  pm1Buffer[pmBufferIndex] = pm1;
  pm25Buffer[pmBufferIndex] = pm25;
  pm10Buffer[pmBufferIndex] = pm10;
  pmBufferIndex = (pmBufferIndex + 1) % PM_FILTER_SIZE;
  if (pmBufferCount < PM_FILTER_SIZE) pmBufferCount++;
}

int averageBuffer(const int* buffer, int count) {
  if (count <= 0) return 0;
  long sum = 0;
  for (int i = 0; i < count; i++) sum += buffer[i];
  return (int)(sum / count);
}

void clearBox(int x, int y, int w, int h) {
  M5.Lcd.fillRect(x, y, w, h, C_BG);
}

String getUtcTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 100)) {
    timeSynced = false;
    return "";
  }
  timeSynced = true;
  char buf[24];
  strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &timeinfo);
  return String(buf);
}

void syncTimeIfNeeded(bool force = false) {
  if (WiFi.status() != WL_CONNECTED) return;
  if (!force && timeSynced) return;
  if (!force && millis() - lastNtpSyncAttempt < NTP_RETRY_INTERVAL_MS) return;

  lastNtpSyncAttempt = millis();
  configTime(0, 0, "pool.ntp.org", "time.google.com", "time.windows.com");
  String ts = getUtcTimestamp();
  if (ts.length() > 0) {
    timeSynced = true;
  }
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.begin(ssid, password);
}

void checkWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    syncTimeIfNeeded();
    return;
  }
  if (millis() - lastWiFiCheck >= WIFI_RETRY_INTERVAL_MS) {
    lastWiFiCheck = millis();
    WiFi.disconnect(true, true);
    delay(200);
    WiFi.begin(ssid, password);
  }
}

void readSHT31() {
  float t = sht31.readTemperature();
  float h = sht31.readHumidity();

  if (isnan(t) || isnan(h)) {
    currentData.shtOk = false;
    return;
  }

  currentData.temperature = t;
  currentData.humidity = h;
  currentData.shtOk = true;
}

void readPMS() {
  pms.updateFrame();

  if (pms.hasNewData()) {
    int rawPm1 = pms.getPM_1_0();
    int rawPm25 = pms.getPM_2_5();
    int rawPm10 = pms.getPM_10_0();

    addPMToBuffer(rawPm1, rawPm25, rawPm10);

    currentData.pm1 = averageBuffer(pm1Buffer, pmBufferCount);
    currentData.pm25 = averageBuffer(pm25Buffer, pmBufferCount);
    currentData.pm10 = averageBuffer(pm10Buffer, pmBufferCount);

    currentData.pc03 = pms.getRawGreaterThan_0_3();
    currentData.pc05 = pms.getRawGreaterThan_0_5();
    currentData.pc10 = pms.getRawGreaterThan_1_0();
    currentData.pc25 = pms.getRawGreaterThan_2_5();
    currentData.pc50 = pms.getRawGreaterThan_5_0();
    currentData.pc100 = pms.getRawGreaterThan_10_0();

    currentData.pmsOk = true;
    lastPmsDataTime = millis();
  }

  if (millis() - lastPmsDataTime > PMS_TIMEOUT_MS) {
    currentData.pmsOk = false;
  }
}

void readSensors() {
  readSHT31();
  readPMS();
  currentData.hasValidData = currentData.shtOk || currentData.pmsOk;
}

bool sendToServer(const SensorData& data) {
  if (!serverEnabled) return false;
  if (WiFi.status() != WL_CONNECTED) {
    lastPostSuccess = false;
    lastHttpCode = 0;
    lastServerReason = "NO WIFI";
    return false;
  }
  if (!data.hasValidData) {
    lastPostSuccess = false;
    lastHttpCode = 0;
    lastServerReason = "NO DATA";
    return false;
  }

  syncTimeIfNeeded();
  sendingNow = true;

  WiFiClientSecure client;
  client.setInsecure();

  HTTPClient http;
  http.begin(client, serverURL);
  http.setTimeout(4000);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<640> doc;
  doc["device_uid"] = deviceUid;

  String sentAt = getUtcTimestamp();
  if (sentAt.length() > 0) {
    doc["sent_at_utc"] = sentAt;
  }

  if (data.shtOk) {
    doc["temperature"] = data.temperature;
    doc["humidity"] = data.humidity;
  } else {
    doc["temperature"] = nullptr;
    doc["humidity"] = nullptr;
  }

  if (data.pmsOk) {
    doc["pm1"] = data.pm1;
    doc["pm25"] = data.pm25;
    doc["pm10"] = data.pm10;
    doc["pc0_3"] = data.pc03;
    doc["pc0_5"] = data.pc05;
    doc["pc1_0"] = data.pc10;
    doc["pc2_5"] = data.pc25;
    doc["pc5_0"] = data.pc50;
    doc["pc10"]  = data.pc100;
  } else {
    doc["pm1"] = nullptr;
    doc["pm25"] = nullptr;
    doc["pm10"] = nullptr;
    doc["pc0_3"] = nullptr;
    doc["pc0_5"] = nullptr;
    doc["pc1_0"] = nullptr;
    doc["pc2_5"] = nullptr;
    doc["pc5_0"] = nullptr;
    doc["pc10"]  = nullptr;
  }

  String payload;
  serializeJson(doc, payload);

  int code = http.POST(payload);
  String response = http.getString();

  lastHttpCode = code;
  lastPostSuccess = (code > 0 && code < 300);

  Serial.printf("[HTTP] code = %d\n", code);
  Serial.println(response);

  if (code == 409) {
    lastServerReason = "WAIT START";
  } else if (code > 0 && code < 300) {
    lastServerReason = "MEASURE";
  } else if (code <= 0) {
    lastServerReason = "NET FAIL";
  } else {
    lastServerReason = "HTTP " + String(code);
  }

  http.end();
  sendingNow = false;

  if (lastPostSuccess) {
    lastSuccessPostTime = millis();
    setStatusMessage("SENT OK");
  } else if (code == 409) {
    setStatusMessage("WAIT START", 1800);
  } else {
    setStatusMessage("SEND ERR", 1800);
  }

  return lastPostSuccess;
}

void drawTopBarStatic() {
  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(WHITE, C_BG);
  M5.Lcd.setCursor(8, 4);
  M5.Lcd.print("AirMonitor");
}

void updateTopBarDynamic() {
  clearBox(200, 0, 120, 20);
  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(WHITE, C_BG);
  M5.Lcd.setCursor(200, 4);
  M5.Lcd.printf("WiFi %s", getWiFiStatusText().c_str());

  M5.Lcd.fillCircle(307, 12, 5, getStatusDotColor());
}

void drawHintRowStatic() {
  M5.Lcd.setTextSize(1);
  M5.Lcd.setTextColor(DARKGREY, C_BG);

  M5.Lcd.setCursor(10, 202);
  M5.Lcd.print("A Next");

  M5.Lcd.setCursor(128, 202);
  M5.Lcd.print("B Send");

  M5.Lcd.setCursor(245, 202);
  M5.Lcd.print("C Auto");
}

void updateBottomBarDynamic() {
  clearBox(0, 218, 320, 22);
  M5.Lcd.drawFastHLine(0, 218, 320, DARKGREY);

  M5.Lcd.setTextSize(1);
  M5.Lcd.setTextColor(WHITE, C_BG);

  M5.Lcd.setCursor(6, 225);
  M5.Lcd.print("SRV ");
  M5.Lcd.print(getServerStatusText());

  M5.Lcd.setCursor(78, 225);
  M5.Lcd.print("Last ");
  M5.Lcd.print(shortAgo(lastSuccessPostTime));

  M5.Lcd.setCursor(150, 225);
  if (millis() < statusMessageUntil) M5.Lcd.print(statusMessage);
  else M5.Lcd.print(lastServerReason);
}

void drawMainScreenStatic() {
  M5.Lcd.fillScreen(C_BG);
  drawTopBarStatic();

  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(C_SUB, C_BG);

  M5.Lcd.setCursor(10, 34);
  M5.Lcd.print("PM2.5");

  M5.Lcd.setCursor(205, 34);
  M5.Lcd.print("AIR");

  M5.Lcd.setCursor(10, 106);
  M5.Lcd.print("TEMP");

  M5.Lcd.setCursor(170, 106);
  M5.Lcd.print("HUM");

  M5.Lcd.setCursor(10, 154);
  M5.Lcd.print("PM1");

  M5.Lcd.setCursor(170, 154);
  M5.Lcd.print("PM10");

  drawHintRowStatic();
  updateTopBarDynamic();
  updateBottomBarDynamic();
}

void updateMainScreenDynamic() {
  updateTopBarDynamic();
  updateBottomBarDynamic();

  clearBox(10, 58, 170, 46);
  clearBox(205, 58, 110, 36);
  clearBox(10, 126, 130, 26);
  clearBox(170, 126, 130, 26);
  clearBox(10, 174, 130, 26);
  clearBox(170, 174, 130, 26);

  if (currentData.pmsOk) {
    M5.Lcd.setTextSize(5);
    M5.Lcd.setTextColor(getAQColor(currentData.pm25), C_BG);
    M5.Lcd.setCursor(10, 58);
    M5.Lcd.printf("%d", currentData.pm25);

    M5.Lcd.setTextSize(2);
    M5.Lcd.setTextColor(getAQColor(currentData.pm25), C_BG);
    M5.Lcd.setCursor(205, 64);
    M5.Lcd.print(getAirQualityLabel(currentData.pm25));
  } else {
    M5.Lcd.setTextSize(5);
    M5.Lcd.setTextColor(C_SUB, C_BG);
    M5.Lcd.setCursor(10, 58);
    M5.Lcd.print("--");

    M5.Lcd.setTextSize(2);
    M5.Lcd.setCursor(205, 64);
    M5.Lcd.print("NO DATA");
  }

  M5.Lcd.setTextSize(3);

  M5.Lcd.setTextColor(CYAN, C_BG);
  M5.Lcd.setCursor(10, 126);
  if (currentData.shtOk) M5.Lcd.printf("%.1f", currentData.temperature);
  else M5.Lcd.print("--");

  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(C_SUB, C_BG);
  M5.Lcd.setCursor(98, 132);
  M5.Lcd.print("C");

  M5.Lcd.setTextSize(3);
  M5.Lcd.setTextColor(YELLOW, C_BG);
  M5.Lcd.setCursor(170, 126);
  if (currentData.shtOk) M5.Lcd.printf("%.1f", currentData.humidity);
  else M5.Lcd.print("--");

  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(C_SUB, C_BG);
  M5.Lcd.setCursor(258, 132);
  M5.Lcd.print("%");

  M5.Lcd.setTextSize(3);
  M5.Lcd.setTextColor(GREEN, C_BG);
  M5.Lcd.setCursor(10, 174);
  if (currentData.pmsOk) M5.Lcd.printf("%d", currentData.pm1);
  else M5.Lcd.print("--");

  M5.Lcd.setTextColor(cOrange(), C_BG);
  M5.Lcd.setCursor(170, 174);
  if (currentData.pmsOk) M5.Lcd.printf("%d", currentData.pm10);
  else M5.Lcd.print("--");
}

void drawParticlesScreenStatic() {
  M5.Lcd.fillScreen(C_BG);
  drawTopBarStatic();

  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(WHITE, C_BG);
  M5.Lcd.setCursor(10, 34);
  M5.Lcd.print("PARTICLES");

  M5.Lcd.setTextColor(C_SUB, C_BG);
  M5.Lcd.setCursor(10, 64);   M5.Lcd.print("0.3");
  M5.Lcd.setCursor(10, 86);   M5.Lcd.print("0.5");
  M5.Lcd.setCursor(10, 108);  M5.Lcd.print("1.0");
  M5.Lcd.setCursor(10, 130);  M5.Lcd.print("2.5");
  M5.Lcd.setCursor(10, 152);  M5.Lcd.print("5.0");
  M5.Lcd.setCursor(10, 174);  M5.Lcd.print("10");

  drawHintRowStatic();
  updateTopBarDynamic();
  updateBottomBarDynamic();
}

void updateParticlesScreenDynamic() {
  updateTopBarDynamic();
  updateBottomBarDynamic();

  clearBox(110, 60, 180, 130);

  M5.Lcd.setTextSize(2);
  if (currentData.pmsOk) {
    M5.Lcd.setTextColor(WHITE, C_BG);
    M5.Lcd.setCursor(110, 64);  M5.Lcd.printf("%d", currentData.pc03);
    M5.Lcd.setCursor(110, 86);  M5.Lcd.printf("%d", currentData.pc05);
    M5.Lcd.setCursor(110, 108); M5.Lcd.printf("%d", currentData.pc10);
    M5.Lcd.setCursor(110, 130); M5.Lcd.printf("%d", currentData.pc25);
    M5.Lcd.setCursor(110, 152); M5.Lcd.printf("%d", currentData.pc50);
    M5.Lcd.setCursor(110, 174); M5.Lcd.printf("%d", currentData.pc100);
  } else {
    M5.Lcd.setTextColor(RED, C_BG);
    M5.Lcd.setCursor(110, 118);
    M5.Lcd.print("NO DATA");
  }
}

void drawSystemScreenStatic() {
  M5.Lcd.fillScreen(C_BG);
  drawTopBarStatic();

  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(WHITE, C_BG);
  M5.Lcd.setCursor(10, 34);
  M5.Lcd.print("SYSTEM");

  M5.Lcd.setTextColor(C_SUB, C_BG);
  M5.Lcd.setCursor(10, 64);   M5.Lcd.print("WIFI");
  M5.Lcd.setCursor(10, 86);   M5.Lcd.print("SERVER");
  M5.Lcd.setCursor(10, 108);  M5.Lcd.print("HTTP");
  M5.Lcd.setCursor(10, 130);  M5.Lcd.print("LAST OK");
  M5.Lcd.setCursor(10, 152);  M5.Lcd.print("SHT31");
  M5.Lcd.setCursor(10, 174);  M5.Lcd.print("PMSA003");

  drawHintRowStatic();
  updateTopBarDynamic();
  updateBottomBarDynamic();
}

void updateSystemScreenDynamic() {
  updateTopBarDynamic();
  updateBottomBarDynamic();

  clearBox(130, 60, 170, 130);

  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(WHITE, C_BG);

  M5.Lcd.setCursor(130, 64);  M5.Lcd.print(getWiFiStatusText());
  M5.Lcd.setCursor(130, 86);  M5.Lcd.print(getServerStatusText());
  M5.Lcd.setCursor(130, 108); M5.Lcd.printf("%d", lastHttpCode);
  M5.Lcd.setCursor(130, 130); M5.Lcd.print(shortAgo(lastSuccessPostTime));
  M5.Lcd.setCursor(130, 152); M5.Lcd.print(currentData.shtOk ? "OK" : "ERR");
  M5.Lcd.setCursor(130, 174); M5.Lcd.print(currentData.pmsOk ? "OK" : "ERR");
}

void drawScreenStatic() {
  if (currentScreen == 0) drawMainScreenStatic();
  else if (currentScreen == 1) drawParticlesScreenStatic();
  else drawSystemScreenStatic();
}

void updateScreenDynamic() {
  if (currentScreen == 0) updateMainScreenDynamic();
  else if (currentScreen == 1) updateParticlesScreenDynamic();
  else updateSystemScreenDynamic();
}

void handleButtons() {
  M5.update();

  if (M5.BtnA.wasPressed()) {
    currentScreen = (currentScreen + 1) % 3;
    setStatusMessage("SCREEN " + String(currentScreen + 1));
    drawScreenStatic();
    updateScreenDynamic();
  }

  if (M5.BtnB.wasPressed()) {
    setStatusMessage("MANUAL SEND");
    readSensors();
    updateScreenDynamic();
    sendToServer(currentData);
    updateScreenDynamic();
  }

  if (M5.BtnC.wasPressed()) {
    serverEnabled = !serverEnabled;
    setStatusMessage(serverEnabled ? "AUTO ON" : "AUTO OFF");
    updateScreenDynamic();
  }
}

void setup() {
  M5.begin();
  Serial.begin(115200);

  M5.Lcd.setRotation(1);
  M5.Lcd.fillScreen(BLACK);

  WiFi.mode(WIFI_STA);
  connectWiFi();

  if (!sht31.begin(0x44)) {
    currentData.shtOk = false;
  }

  Serial2.begin(9600, SERIAL_8N1, PMS_RX_PIN, PMS_TX_PIN);
  pms.init(&Serial2);

  lastWiFiCheck = millis();
  lastSensorRead = millis();
  lastUIRefresh = 0;
  lastSendTime = millis();
  lastPmsDataTime = millis();

  drawScreenStatic();
  updateScreenDynamic();
}

void loop() {
  handleButtons();
  checkWiFi();

  unsigned long now = millis();

  if (now - lastSensorRead >= SENSOR_READ_INTERVAL_MS) {
    lastSensorRead = now;
    readSensors();
  }

  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;
    updateScreenDynamic();
    sendToServer(currentData);
    updateScreenDynamic();
  }

  if (now - lastUIRefresh >= UI_REFRESH_MS) {
    lastUIRefresh = now;
    updateScreenDynamic();
  }

  delay(20);
}
