/*
 * SENTINEL — Addressable ESP32 Zone Concentrator Firmware (Wokwi & Field Ready)
 * Official Title: Microcontroller-Based Acoustic-Visual Threat Detection and
 * Evacuation Simulation for Sto. Niño Senior High School, Tacloban City
 *
 * NeoPixel 16-LED Address Map:
 *   LEDs 0..3  -> Tech Pro Building (TPB F1..F4)
 *   LEDs 4..7  -> Academic Building (AB F1..F4)
 *   LEDs 8..9  -> Laboratory Building (LB F1..F2)
 *   LED  10    -> Perimeter Gate-W
 *   LED  11    -> Perimeter Gate-NE
 *   LEDs 12..15-> Global Campus Status Beacon
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ── Network & MQTT Broker ───────────────────────────────────────────────────
const char* WIFI_SSID   = "Wokwi-GUEST";
const char* WIFI_PASS   = "";
const char* MQTT_BROKER = "broker.hivemq.com";
const int   MQTT_PORT   = 1883;

const char* TOPIC_STATE   = "stonino/campus/state";
const char* TOPIC_ACK     = "stonino/campus/device/ack";
const char* TOPIC_TRIGGER = "stonino/campus/device/trigger";
const char* DEVICE_ID     = "ESP32-CAMPUS-GW01";

// ── GPIO Pins ───────────────────────────────────────────────────────────────
#define PIN_NEOPIXEL   4
#define NUM_PIXELS     16
#define PIN_BUZZER     25
#define PIN_BTN_THREAT 26
#define PIN_BTN_RESET  27
#define PIN_MIC_POT    34

WiFiClient espClient;
PubSubClient mqtt(espClient);
Adafruit_NeoPixel ring(NUM_PIXELS, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);
Adafruit_SSD1306 oled(128, 64, &Wire, -1);

// ── Live Campus State Mirror ────────────────────────────────────────────────
String campusStatus = "NORMAL";
String evacGate     = "BOTH";
String buzzerMode   = "OFF";
String floorCodes[10] = {"S","S","S","S","S","S","S","S","S","S"};
bool gateWOpen  = true;
bool gateNEOpen = true;
int  safeCount  = 36;
int  holdCount  = 0;
int  critCount  = 0;
int  pktSeq     = 0;

unsigned long lastHeartbeat   = 0;
unsigned long lastAnimTick    = 0;
unsigned long lastBtnCheck    = 0;
unsigned long lastOledUpdate  = 0;
bool blinkPhase = false;
bool lastThreatBtn = HIGH;
bool lastResetBtn  = HIGH;
bool potTriggered  = false;

void updateOLED() {
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);

  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.print("SENTINEL ");
  oled.println(mqtt.connected() ? "[ONLINE]" : "[SYNC]");

  oled.drawLine(0, 10, 127, 10, SSD1306_WHITE);

  oled.setTextSize(2);
  oled.setCursor(0, 15);
  oled.println(campusStatus);

  oled.setTextSize(1);
  oled.setCursor(0, 36);
  oled.print("EVAC: ");
  oled.println(evacGate);

  oled.setCursor(0, 46);
  oled.printf("W:%s  NE:%s", gateWOpen ? "OPEN" : "LOCK", gateNEOpen ? "OPEN" : "LOCK");

  oled.setCursor(0, 56);
  oled.printf("S:%d H:%d T:%d #%d", safeCount, holdCount, critCount, pktSeq);

  oled.display();
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<1024> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.print("JSON parse error: ");
    Serial.println(err.c_str());
    return;
  }

  campusStatus = doc["status"] | "NORMAL";
  evacGate     = doc["evac_gate"] | "BOTH";
  buzzerMode   = doc["buzzer"] | "OFF";
  pktSeq       = doc["seq"] | 0;

  const char* gW  = doc["gates"]["W"] | "OPEN";
  const char* gNE = doc["gates"]["NE"] | "OPEN";
  gateWOpen  = (String(gW) == "OPEN");
  gateNEOpen = (String(gNE) == "OPEN");

  safeCount = doc["counts"]["safe"] | 36;
  holdCount = doc["counts"]["hold"] | 0;
  critCount = doc["counts"]["blocked"] | 0;

  JsonArray floors = doc["floors"];
  for (int i = 0; i < 10 && i < (int)floors.size(); i++) {
    floorCodes[i] = floors[i].as<String>();
  }

  updateOLED();
  Serial.printf("[MQTT RX] Seq=%d Status=%s Evac=%s\n", pktSeq, campusStatus.c_str(), evacGate.c_str());
}

void publishHeartbeat() {
  int rawPot = analogRead(PIN_MIC_POT);
  float acousticDb = map(rawPot, 0, 4095, 15, 98);

  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["online"]    = true;
  doc["rssi"]      = WiFi.RSSI();
  doc["acoustic"]  = acousticDb;
  doc["firmware"]  = "SENTINEL-GW-v2.1";
  doc["seq"]       = pktSeq;

  char buf[256];
  serializeJson(doc, buf);
  mqtt.publish(TOPIC_ACK, buf, true);
}

void publishEdgeTrigger(const char* action, float acousticVal) {
  StaticJsonDocument<256> doc;
  doc["device_id"]     = DEVICE_ID;
  doc["action"]        = action;
  doc["target_device"] = "TPB-F1-CAM-L";
  doc["acoustic"]      = acousticVal;
  doc["pose"]          = 78.0;
  doc["object"]        = 88.0;
  doc["source"]        = "wokwi_esp32_panel";

  char buf[256];
  serializeJson(doc, buf);
  mqtt.publish(TOPIC_TRIGGER, buf);
  Serial.printf("[MQTT TX] %s -> %s\n", TOPIC_TRIGGER, buf);
}

void reconnectMqtt() {
  if (mqtt.connected()) return;
  String clientId = "snshs-gw-" + String(random(0xffff), HEX);
  const char* lwtPayload = "{\"device_id\":\"ESP32-CAMPUS-GW01\",\"online\":false}";

  if (mqtt.connect(clientId.c_str(), nullptr, nullptr, TOPIC_ACK, 1, true, lwtPayload)) {
    mqtt.subscribe(TOPIC_STATE, 1);
    publishHeartbeat();
    updateOLED();
    Serial.println("MQTT Connected to HiveMQ!");
  }
}

uint32_t colorForCode(const String& code, bool phase) {
  if (code == "T") {
    return phase ? ring.Color(255, 15, 15) : ring.Color(60, 0, 0);
  }
  if (code == "H") {
    return phase ? ring.Color(255, 150, 0) : ring.Color(40, 20, 0);
  }
  if (code == "U") {
    return ring.Color(65, 75, 90);
  }
  return ring.Color(0, 175, 70);
}

void updateLedsAndBuzzer() {
  blinkPhase = !blinkPhase;

  // LEDs 0..9 -> 10 Floors (TPB F1..F4, AB F1..F4, LB F1..F2)
  for (int i = 0; i < 10; i++) {
    ring.setPixelColor(i, colorForCode(floorCodes[i], blinkPhase));
  }
  // LED 10 -> GATE-W, LED 11 -> GATE-NE
  ring.setPixelColor(10, gateWOpen  ? ring.Color(0, 185, 80) : ring.Color(255, 0, 0));
  ring.setPixelColor(11, gateNEOpen ? ring.Color(0, 185, 80) : ring.Color(255, 0, 0));

  // LEDs 12..15 -> Campus Global Beacon
  uint32_t gCol = ring.Color(0, 175, 70);
  if (campusStatus == "CRITICAL") {
    gCol = blinkPhase ? ring.Color(255, 0, 0) : ring.Color(20, 0, 0);
  } else if (campusStatus == "WARNING") {
    gCol = blinkPhase ? ring.Color(255, 140, 0) : ring.Color(30, 15, 0);
  }
  for (int i = 12; i < NUM_PIXELS; i++) {
    ring.setPixelColor(i, gCol);
  }
  ring.show();

  // Non-blocking Buzzer Cadence
  if (buzzerMode == "ALARM") {
    if (blinkPhase) tone(PIN_BUZZER, 2200);
    else tone(PIN_BUZZER, 1650);
  } else if (buzzerMode == "CHIRP") {
    if (blinkPhase) tone(PIN_BUZZER, 1200);
    else noTone(PIN_BUZZER);
  } else {
    noTone(PIN_BUZZER);
  }
}

void setup() {
  Serial.begin(115200);
  randomSeed(esp_random());

  pinMode(PIN_BTN_THREAT, INPUT_PULLUP);
  pinMode(PIN_BTN_RESET, INPUT_PULLUP);
  pinMode(PIN_BUZZER, OUTPUT);

  ring.begin();
  ring.setBrightness(110);
  ring.show();

  Wire.begin(21, 22);
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  updateOLED();

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected!");

  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  mqtt.setKeepAlive(60);
  mqtt.setBufferSize(1024);
}

void loop() {
  if (!mqtt.connected()) {
    reconnectMqtt();
  }
  mqtt.loop();

  unsigned long now = millis();

  if (now - lastAnimTick >= 350) {
    lastAnimTick = now;
    updateLedsAndBuzzer();
  }

  if (now - lastHeartbeat >= 5000) {
    lastHeartbeat = now;
    if (mqtt.connected()) {
      publishHeartbeat();
    }
  }

  if (now - lastBtnCheck >= 120) {
    lastBtnCheck = now;
    bool tBtn = digitalRead(PIN_BTN_THREAT);
    bool rBtn = digitalRead(PIN_BTN_RESET);
    int rawPot = analogRead(PIN_MIC_POT);
    float dbVal = map(rawPot, 0, 4095, 15, 98);

    if (lastThreatBtn == HIGH && tBtn == LOW && mqtt.connected()) {
      publishEdgeTrigger("TRIGGER", max(dbVal, 88.0f));
    }
    if (lastResetBtn == HIGH && rBtn == LOW && mqtt.connected()) {
      potTriggered = false;
      publishEdgeTrigger("RESET", dbVal);
    }
    if (dbVal >= 85.0f && !potTriggered && mqtt.connected()) {
      potTriggered = true;
      publishEdgeTrigger("TRIGGER", dbVal);
    } else if (dbVal < 60.0f) {
      potTriggered = false;
    }

    lastThreatBtn = tBtn;
    lastResetBtn  = rBtn;
  }

  if (now - lastOledUpdate >= 2000) {
    lastOledUpdate = now;
    updateOLED();
  }
}
