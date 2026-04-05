#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <WebServer.h>
#include <SPIFFS.h>

const uint8_t PIN_AUTO_MODE = 4;
const uint8_t PIN_CYCLE_SIGNAL = 5;
const uint8_t PIN_LED = 2;

const char *ssid = "udsb-nova";
const char *password = "udsb2735***";
const char *mqtt_server = "192.168.1.17";
const uint16_t mqtt_port = 1883;
const char *machine_id = "A1";

const uint32_t POLL_INTERVAL_MS = 5;
const uint32_t DEBOUNCE_MS = 10;
const uint32_t WIFI_RETRY_DELAY_MS = 500;
const uint32_t MQTT_RETRY_DELAY_MS = 2000;
const uint32_t MAX_DOWNTIME_MS = 5UL * 60UL * 60UL * 1000UL;

const String command_topic = String("machines/") + machine_id;
const String status_publish_topic = String("status/") + machine_id;
const char *cycle_topic = "machine/cycle_time";
const char *job_end_topic = "action/job_end";
const char *get_mpid_topic = "action/get_mpid";
const char *override_topic = "overide/off";
const char *log_file_path = "/cycle_log.txt";

WebServer server(80);
WiFiClient espClient;
PubSubClient mqttClient(espClient);

char client_id[32];
portMUX_TYPE stateMux = portMUX_INITIALIZER_UNLOCKED;

struct CycleEvent {
  float elapsedSeconds;
  int mainId;
  int mpId;
  int actionCode;
  char action[20];
};

QueueHandle_t eventQueue = nullptr;

bool loggingEnabled = false;
bool resetSamplingState = true;
int currentMpId = -1;
int currentMainId = -1;

enum MachineState { IDLE, RUNNING, DOWNTIME };
MachineState currentState = IDLE;
uint32_t cycleStartMs = 0;
uint32_t downtimeStartMs = 0;
bool downtimeTimerRunning = false;

void connectWiFi();
void checkWiFiReconnect();
void connectMQTT();
void checkMQTTReconnect();
void publishStatus(const char *statusText, bool retained = true);
void callback(char *topic, byte *payload, unsigned int length);
void updateMachineStateTask(void *pvParameters);
void startLogging();
void stopLogging();
void stopLoggingOverride();
void resetTrackingState();
void requestSamplingReset();
void startCycleTimer(uint32_t nowMs);
void stopCycleTimer(uint32_t nowMs, const char *reason);
void startDowntimeTimer(uint32_t nowMs);
void stopDowntimeTimer(uint32_t nowMs, const char *reason = "downtime");
void checkDowntimeTimer();
bool publishCycleEvent(const CycleEvent &event);
void appendEventToSpiffs(const CycleEvent &event);
void queueCycleEvent(float elapsedSeconds, const char *action);
void publishJobEnd();
void requestCurrentRunIds();
void blinkLed(uint16_t durationMs = 100);
void drainEventQueue();

int actionCodeFromName(const char *action) {
  if (strcmp(action, "normal_cycle") == 0) {
    return 0;
  }
  if (strcmp(action, "downtime") == 0) {
    return 1;
  }
  if (strcmp(action, "abnormal_cycle") == 0) {
    return 2;
  }
  if (strcmp(action, "forced_stop") == 0) {
    return 3;
  }
  return -1;
}

void blinkLed(uint16_t durationMs) {
  digitalWrite(PIN_LED, HIGH);
  delay(durationMs);
  digitalWrite(PIN_LED, LOW);
}

void publishStatus(const char *statusText, bool retained) {
  if (!mqttClient.connected()) {
    return;
  }

  StaticJsonDocument<96> doc;
  doc["status"] = statusText;
  doc["machineid"] = machine_id;

  char payload[96];
  serializeJson(doc, payload, sizeof(payload));
  mqttClient.publish(status_publish_topic.c_str(), payload, retained);
  Serial.print("Status published: ");
  Serial.println(payload);
}

void resetTrackingState() {
  portENTER_CRITICAL(&stateMux);
  currentState = IDLE;
  cycleStartMs = 0;
  downtimeStartMs = 0;
  downtimeTimerRunning = false;
  portEXIT_CRITICAL(&stateMux);
}

void requestSamplingReset() {
  portENTER_CRITICAL(&stateMux);
  resetSamplingState = true;
  portEXIT_CRITICAL(&stateMux);
}

void startCycleTimer(uint32_t nowMs) {
  portENTER_CRITICAL(&stateMux);
  currentState = RUNNING;
  cycleStartMs = nowMs;
  portEXIT_CRITICAL(&stateMux);
  Serial.println("Normal cycle timer started");
}

void startDowntimeTimer(uint32_t nowMs) {
  portENTER_CRITICAL(&stateMux);
  if (!downtimeTimerRunning) {
    downtimeStartMs = nowMs;
    downtimeTimerRunning = true;
    currentState = DOWNTIME;
  }
  portEXIT_CRITICAL(&stateMux);
}

void queueCycleEvent(float elapsedSeconds, const char *action) {
  bool loggingActive;
  int mainId;
  int mpId;

  portENTER_CRITICAL(&stateMux);
  loggingActive = loggingEnabled;
  mainId = currentMainId;
  mpId = currentMpId;
  portEXIT_CRITICAL(&stateMux);

  if (!loggingActive) {
    return;
  }

  if (mainId < 0 || mpId < 0) {
    Serial.println("Skipping event because main_id/mp_id is not initialized");
    return;
  }

  CycleEvent event = {};
  event.elapsedSeconds = elapsedSeconds;
  event.mainId = mainId;
  event.mpId = mpId;
  event.actionCode = actionCodeFromName(action);
  strlcpy(event.action, action, sizeof(event.action));

  if (xQueueSend(eventQueue, &event, 0) != pdPASS) {
    Serial.println("Event queue full, appending directly to SPIFFS");
    appendEventToSpiffs(event);
  }
}

void stopCycleTimer(uint32_t nowMs, const char *reason) {
  uint32_t startedAt = 0;

  portENTER_CRITICAL(&stateMux);
  if (currentState == RUNNING && cycleStartMs != 0) {
    startedAt = cycleStartMs;
    currentState = IDLE;
    cycleStartMs = 0;
  }
  portEXIT_CRITICAL(&stateMux);

  if (startedAt == 0) {
    return;
  }

  float elapsedSeconds = (nowMs - startedAt) / 1000.0f;
  Serial.print("Cycle timer stopped - ");
  Serial.println(reason);
  Serial.print("Elapsed seconds: ");
  Serial.println(elapsedSeconds);
  queueCycleEvent(elapsedSeconds, reason);
}

void stopDowntimeTimer(uint32_t nowMs, const char *reason) {
  uint32_t startedAt = 0;

  portENTER_CRITICAL(&stateMux);
  if (downtimeTimerRunning && downtimeStartMs != 0) {
    startedAt = downtimeStartMs;
    downtimeTimerRunning = false;
    downtimeStartMs = 0;
    currentState = IDLE;
  }
  portEXIT_CRITICAL(&stateMux);

  if (startedAt == 0) {
    return;
  }

  float elapsedSeconds = (nowMs - startedAt) / 1000.0f;
  Serial.print("Downtime timer stopped, seconds: ");
  Serial.println(elapsedSeconds);
  queueCycleEvent(elapsedSeconds, reason);
}

bool publishCycleEvent(const CycleEvent &event) {
  if (!mqttClient.connected()) {
    return false;
  }

  StaticJsonDocument<192> doc;
  doc["elapsed_time_ms"] = event.elapsedSeconds;
  doc["main_id"] = event.mainId;
  doc["mp_id"] = event.mpId;
  doc["machineid"] = machine_id;
  doc["action"] = event.action;

  char payload[192];
  serializeJson(doc, payload, sizeof(payload));
  bool ok = mqttClient.publish(cycle_topic, payload);
  if (ok) {
    Serial.print("MQTT event published: ");
    Serial.println(payload);
  }
  return ok;
}

void appendEventToSpiffs(const CycleEvent &event) {
  File file = SPIFFS.open(log_file_path, FILE_APPEND);
  if (!file) {
    Serial.println("Failed to open log file for append");
    return;
  }

  char line[96];
  snprintf(
      line,
      sizeof(line),
      "%.3f,%d,%d,%d,%s\n",
      event.elapsedSeconds,
      event.mainId,
      event.mpId,
      event.actionCode,
      event.action);

  file.print(line);
  file.close();
  Serial.print("Logged to SPIFFS: ");
  Serial.println(line);
}

void requestCurrentRunIds() {
  if (!mqttClient.connected()) {
    return;
  }

  StaticJsonDocument<64> doc;
  doc["machine_id"] = machine_id;

  char payload[64];
  serializeJson(doc, payload, sizeof(payload));
  mqttClient.publish(get_mpid_topic, payload);
  Serial.print("Requested current run ids: ");
  Serial.println(payload);
}

void publishJobEnd() {
  if (!mqttClient.connected()) {
    return;
  }

  int mpId;
  portENTER_CRITICAL(&stateMux);
  mpId = currentMpId;
  portEXIT_CRITICAL(&stateMux);

  if (mpId < 0) {
    return;
  }

  StaticJsonDocument<64> doc;
  doc["mp_id"] = mpId;

  char payload[64];
  serializeJson(doc, payload, sizeof(payload));
  mqttClient.publish(job_end_topic, payload);
  Serial.print("MQTT job_end published: ");
  Serial.println(payload);
}

void startLogging() {
  Serial.println("Start logging");
  portENTER_CRITICAL(&stateMux);
  loggingEnabled = true;
  portEXIT_CRITICAL(&stateMux);

  resetTrackingState();
  requestSamplingReset();
  requestCurrentRunIds();
  blinkLed();
}

void stopLogging() {
  Serial.println("Stop logging");
  portENTER_CRITICAL(&stateMux);
  loggingEnabled = false;
  portEXIT_CRITICAL(&stateMux);

  resetTrackingState();
  publishJobEnd();
  blinkLed();
}

void stopLoggingOverride() {
  Serial.println("Stop logging override");
  portENTER_CRITICAL(&stateMux);
  loggingEnabled = false;
  portEXIT_CRITICAL(&stateMux);

  resetTrackingState();

  if (mqttClient.connected()) {
    StaticJsonDocument<64> doc;
    doc["machine_id"] = machine_id;
    char payload[64];
    serializeJson(doc, payload, sizeof(payload));
    mqttClient.publish(override_topic, payload);
    Serial.print("MQTT override published: ");
    Serial.println(payload);
  }

  blinkLed();
}

void connectWiFi() {
  Serial.print("Connecting to WiFi...");
  WiFi.begin(ssid, password);

  uint8_t attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    delay(WIFI_RETRY_DELAY_MS);
    Serial.print('.');
    attempts++;
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWiFi connection failed. Restarting...");
    delay(1000);
    ESP.restart();
    return;
  }

  Serial.println("\nWiFi connected");
  Serial.println(WiFi.localIP());
}

void checkWiFiReconnect() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  Serial.println("WiFi disconnected. Reconnecting...");
  WiFi.disconnect();
  WiFi.reconnect();

  uint8_t attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 10) {
    delay(WIFI_RETRY_DELAY_MS);
    Serial.print('.');
    attempts++;
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWiFi reconnect failed. Restarting...");
    ESP.restart();
    return;
  }

  Serial.println("\nWiFi reconnected");
}

void connectMQTT() {
  uint8_t retries = 0;

  while (!mqttClient.connected() && retries < 25) {
    Serial.print("Attempting MQTT connection...");

    StaticJsonDocument<96> willDoc;
    willDoc["status"] = "disconnected";
    willDoc["machineid"] = machine_id;

    char willPayload[96];
    serializeJson(willDoc, willPayload, sizeof(willPayload));

    if (mqttClient.connect(client_id, status_publish_topic.c_str(), 1, true, willPayload)) {
      Serial.println(" connected");
      mqttClient.subscribe(command_topic.c_str());
      publishStatus("connected", true);
      requestCurrentRunIds();
      return;
    }

    Serial.println(" failed, retrying...");
    delay(MQTT_RETRY_DELAY_MS);
    retries++;
  }

  Serial.println("MQTT reconnect failed. Restarting...");
  ESP.restart();
}

void checkMQTTReconnect() {
  if (!mqttClient.connected()) {
    connectMQTT();
  }
}

void callback(char *topic, byte *payload, unsigned int length) {
  Serial.print("Message received on topic: ");
  Serial.println(topic);

  char json[256];
  if (length >= sizeof(json)) {
    length = sizeof(json) - 1;
  }
  memcpy(json, payload, length);
  json[length] = '\0';

  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, json);
  if (error) {
    Serial.print("JSON deserialization failed: ");
    Serial.println(error.c_str());
    return;
  }

  if (doc.containsKey("main_id")) {
    portENTER_CRITICAL(&stateMux);
    currentMainId = doc["main_id"];
    portEXIT_CRITICAL(&stateMux);
  }

  if (doc.containsKey("mp_id")) {
    portENTER_CRITICAL(&stateMux);
    currentMpId = doc["mp_id"];
    portEXIT_CRITICAL(&stateMux);
  }

  const char *command = doc["command"] | "";
  if (command[0] == '\0') {
    Serial.println("Missing command in MQTT payload");
    return;
  }

  if (strcmp(command, "start") == 0 || strcmp(command, "true") == 0) {
    startLogging();
  } else if (strcmp(command, "stop") == 0) {
    stopLogging();
  } else {
    Serial.print("Unknown command: ");
    Serial.println(command);
  }
}

void checkDowntimeTimer() {
  bool shouldStop = false;
  uint32_t startedAt = 0;

  portENTER_CRITICAL(&stateMux);
  if (loggingEnabled && downtimeTimerRunning) {
    startedAt = downtimeStartMs;
    shouldStop = (startedAt != 0 && (millis() - startedAt) >= MAX_DOWNTIME_MS);
  }
  portEXIT_CRITICAL(&stateMux);

  if (shouldStop) {
    Serial.println("Downtime exceeded threshold. Stopping logging...");
    stopLoggingOverride();
  }
}

void drainEventQueue() {
  CycleEvent event;
  while (xQueueReceive(eventQueue, &event, 0) == pdTRUE) {
    bool published = publishCycleEvent(event);
    if (!published) {
      appendEventToSpiffs(event);
    }
  }
}

void updateMachineStateTask(void *pvParameters) {
  bool lastRawAuto = false;
  bool lastRawCycle = false;
  bool stableAuto = false;
  bool stableCycle = false;
  uint32_t autoChangedAt = 0;
  uint32_t cycleChangedAt = 0;

  for (;;) {
    uint32_t nowMs = millis();
    bool rawAuto = (digitalRead(PIN_AUTO_MODE) == LOW);
    bool rawCycle = (digitalRead(PIN_CYCLE_SIGNAL) == LOW);

    bool shouldReset;
    bool loggingActive;

    portENTER_CRITICAL(&stateMux);
    shouldReset = resetSamplingState;
    loggingActive = loggingEnabled;
    if (shouldReset) {
      resetSamplingState = false;
    }
    portEXIT_CRITICAL(&stateMux);

    if (shouldReset) {
      lastRawAuto = rawAuto;
      lastRawCycle = rawCycle;
      stableAuto = rawAuto;
      stableCycle = rawCycle;
      autoChangedAt = nowMs;
      cycleChangedAt = nowMs;
      resetTrackingState();
      if (loggingActive && !stableAuto) {
        startDowntimeTimer(nowMs);
      }
    }

    if (rawAuto != lastRawAuto) {
      lastRawAuto = rawAuto;
      autoChangedAt = nowMs;
    }

    if (rawCycle != lastRawCycle) {
      lastRawCycle = rawCycle;
      cycleChangedAt = nowMs;
    }

    if (!loggingActive) {
      vTaskDelay(pdMS_TO_TICKS(POLL_INTERVAL_MS));
      continue;
    }

    if (rawAuto != stableAuto && (nowMs - autoChangedAt) >= DEBOUNCE_MS) {
      bool previousAuto = stableAuto;
      stableAuto = rawAuto;

      if (previousAuto && !stableAuto) {
        Serial.println("Switched to manual mode");
        stopCycleTimer(nowMs, "abnormal_cycle");
        startDowntimeTimer(nowMs);
      } else if (!previousAuto && stableAuto) {
        Serial.println("Switched to auto mode");
        stopDowntimeTimer(nowMs, "downtime");
      }
    }

    if (rawCycle != stableCycle && (nowMs - cycleChangedAt) >= DEBOUNCE_MS) {
      bool previousCycle = stableCycle;
      stableCycle = rawCycle;

      if (stableAuto) {
        Serial.print("Cycle signal changed to: ");
        Serial.println(stableCycle ? "ACTIVE" : "INACTIVE");

        if (!previousCycle && stableCycle) {
          stopCycleTimer(nowMs, "normal_cycle");
          startCycleTimer(nowMs);
        }
      }
    }

    vTaskDelay(pdMS_TO_TICKS(POLL_INTERVAL_MS));
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_AUTO_MODE, INPUT_PULLUP);
  pinMode(PIN_CYCLE_SIGNAL, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  if (!SPIFFS.begin(true)) {
    Serial.println("SPIFFS mount failed");
  }

  String clientId = String("ESP_") + machine_id;
  clientId.toCharArray(client_id, sizeof(client_id));

  connectWiFi();
  mqttClient.setServer(mqtt_server, mqtt_port);
  mqttClient.setCallback(callback);
  connectMQTT();

  server.on("/log", HTTP_GET, []() {
    File file = SPIFFS.open(log_file_path, FILE_READ);
    if (!file) {
      server.send(404, "text/plain", "Log file not found");
      return;
    }

    server.streamFile(file, "text/plain");
    file.close();
  });

  server.on("/clear_log", HTTP_POST, []() {
    File file = SPIFFS.open(log_file_path, FILE_WRITE);
    if (!file) {
      server.send(500, "text/plain", "Failed to clear log file");
      return;
    }
    file.close();
    server.send(200, "text/plain", "Log file cleared successfully");
  });

  server.begin();

  eventQueue = xQueueCreate(64, sizeof(CycleEvent));
  xTaskCreatePinnedToCore(updateMachineStateTask, "SignalSampler", 4096, nullptr, 2, nullptr, 0);

  requestSamplingReset();
}

void loop() {
  checkWiFiReconnect();
  checkMQTTReconnect();
  mqttClient.loop();
  server.handleClient();
  drainEventQueue();
  checkDowntimeTimer();
  delay(2);
}
