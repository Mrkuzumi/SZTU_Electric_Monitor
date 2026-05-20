#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <Wire.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_GFX.h>

// ===== WiFi =====
const char* WIFI_SSID = "OP_2G";
const char* WIFI_PASS = "12344321";

// ===== 树莓派地址（改成你 Pi 的实际 IP）=====
const char* PI_HOST = "192.168.1.153";
const int   PI_PORT = 8080;

// ===== OLED 接线: SDA→D2(GPIO4), SCL→D1(GPIO5) =====
#define SDA_PIN 4
#define SCL_PIN 5

#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT 64
#define OLED_ADDR     0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// 从多行字符串中取第 n 行（n 从 1 开始）
String readLine(const String& str, int n) {
  int start = 0;
  for (int i = 0; i < n; i++) {
    start = str.indexOf('\n', start);
    if (start < 0) return "?";
    start++;
  }
  int end = str.indexOf('\n', start);
  if (end < 0) end = str.length();
  return str.substring(start, end);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  // 1. OLED 初始化
  Wire.begin(SDA_PIN, SCL_PIN);
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("OLED FAIL");
    while (1) delay(100);
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0, 0);
  display.println("WiFi connecting...");
  display.display();

  // 2. WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 40) {
    delay(500);
    Serial.print(".");
    retry++;
  }

  if (WiFi.status() != WL_CONNECTED) {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("WiFi FAIL");
    display.display();
    while (1) delay(100);
  }

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("WiFi OK");
  display.setCursor(0, 16);
  display.print("PI: ");
  display.print(PI_HOST);
  display.display();
  delay(1500);
}

void fetchAndShow() {
  if (WiFi.status() != WL_CONNECTED) return;

  WiFiClient client;
  HTTPClient http;

  String url = "http://" + String(PI_HOST) + ":" + String(PI_PORT) + "/";
  http.begin(client, url);
  http.setTimeout(15000);

  int code = http.GET();

  if (code != 200) {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.print("HTTP ");
    display.print(code);
    display.display();
    http.end();
    return;
  }

  String body = http.getString();
  http.end();

  if (!body.startsWith("OK")) {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Cookie err");
    display.display();
    return;
  }

  // 解析 OK\n日期\n剩余\n今日用量\n昨日用量
  String dateStr  = readLine(body, 1);
  String remain   = readLine(body, 2);
  String todayUse = readLine(body, 3);
  String yestUse  = readLine(body, 4);

  // ===== OLED 绘制 =====
  display.clearDisplay();

  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print("=== "); display.print(dateStr); display.println(" ===");

  display.drawLine(0, 10, 128, 10, WHITE);

  // 剩余电量 大字体
  display.setTextSize(2);
  display.setCursor(0, 14);
  display.print(remain);
  display.setTextSize(1);
  display.print("kWh");

  // 今日用量
  display.setCursor(0, 38);
  display.print("Tdy: "); display.print(todayUse); display.println(" kWh");

  // 昨日用量
  display.setCursor(0, 48);
  display.print("Ydy: "); display.print(yestUse); display.println(" kWh");

  // 底栏
  display.setCursor(0, 57);
  display.print("via Pi 5min");

  display.display();

  Serial.print("OK "); Serial.print(dateStr);
  Serial.print(" remain="); Serial.print(remain);
  Serial.print(" today="); Serial.println(todayUse);
}

void loop() {
  fetchAndShow();
  delay(5 * 60 * 1000);
}
