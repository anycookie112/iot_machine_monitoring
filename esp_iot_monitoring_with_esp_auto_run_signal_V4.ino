#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// #define RELAY_PIN 2
// #define RELAY_PIN4 4


const int pin4 = 18;         // Pin to monitor
const int pin5 = 19;

//Network Detauils
const char *ssid = "udsb-nova";     // Your WiFi SSID
const char *password = "udsb2735***"; // Your WiFi password



// const char *ssid = "Shua phone";     // Your WiFi SSID
// const char *password = "11111111"; // Your WiFi password

// const char* mqtt_server = "192.168.1.15"; // Local
// const char* mqtt_server = "172.20.10.3"; // Hotspot
const char* mqtt_server = "192.168.1.17"; // Linux Server
// const char* mqtt_server = " 192.168.132.192"; // Host machine IP
const int mqtt_port = 1883;


//Timer Details
// float startTime = 0;  // To store the start time
float elapsedTime = 0; // To store the elapsed time

float downTime = 0; //To store downtime
float elapsedDownTime = 0; //To store elapsed downtime

const unsigned long RESET_INTERVAL = 24UL * 60UL * 60UL * 1000UL;  // 24 hours in milliseconds
// const unsigned long RESET_INTERVAL = 20UL * 1000UL;  // 20 seconds
unsigned long lastResetCheck = 0;  // Track last reset check time


//Flags
bool isTimerRunning = false;   // Flag to track if the timer is running
bool lastState = HIGH;  // Track last signal state
bool waitingForTimer = false;     // True when waiting for the current cycle to end
// bool blockNewCycles = false;      // True to block starting new cycles after current one
bool timeOut = false; //Track first auto run signal from machine
// bool forceTimerStop = false;  // Global flag to force the timer to stop


int pinStateAuto = digitalRead(pin5); 
int pinState = digitalRead(pin4);
    // pinState = digitalRead(pin2);        // Actual machine state
    // pinStateAuto = digitalRead(pin4);
static bool hasTimedOut = false;              // Flag to track timeout state


//MQTT Topics
const char* machine_id = "C6A";   // Machine-specific identifier

const char* mqtt_topic = "machine/checking"; // The topic you want to subscribe to
const char* mqtt_topic_ums = "machine/ums"; // The topic you want to subscribe to
const char* topic_status = "status/C6A";   // Status topic- Send esp status to python and update status of esp in database

String client_id_str = "ESP_" + String(machine_id);
String status_topic = "machines/" + String(machine_id);  // MQTT topic


char client_id[20];  // Fixed-size buffer for client ID

//Variables
int mp_id = -1;
int main_id = -1;
String mould_id = "";
bool status = false;

enum MachineState { IDLE, RUNNING, DOWNTIME };

MachineState currentState = IDLE;
unsigned long startTime = 0;
unsigned long downtimeStart = 0;
bool blockNewCycles = false;
bool forceTimerStop = false;
bool isDowntimeTimerRunning = false;
// const unsigned long MAX_DOWNTIME_MS = 15000; // 15 minutes in milliseconds
const unsigned long MAX_DOWNTIME_MS = 5UL * 60 * 60 * 1000; // 5 hours in milliseconds




WiFiServer server(80);
WiFiClient espClient;
PubSubClient mqttClient(espClient);




void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);

    pinMode(pin5, INPUT); //mould open end
    pinMode(pin4, INPUT); //auto run
    // pinMode(RELAY_PIN, INPUT_PULLDOWN);  // Enable internal pulldown
    // pinMode(RELAY_PIN4, INPUT_PULLDOWN);  // Enable internal pulldown
    // digitalWrite(pinled, LOW);
    delay(10);

    client_id_str.toCharArray(client_id, sizeof(client_id));

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi connected!");
    Serial.println("IP Address: ");
    Serial.println(WiFi.localIP());

    server.begin();
    mqttClient.setCallback(callback);  
    mqttClient.setServer(mqtt_server, mqtt_port);
    
    connectMQTT();  
}



void loop() {
    checkWiFiReconnect();  
    checkMQTTReconnect();  
    mqttClient.loop();    

    // pinStateAuto = digitalRead(RELAY_PIN4); // Read auto/manual state

    if (hasTimedOut && pinStateAuto == HIGH) {  // No need for `== true`
        hasTimedOut = false;  // Reset timeout flag
        restart_esp();        // Restart ESP
    }

    if (status) {  // Avoid infinite while loop
        updateMachineState();
        checkDowntimeTimer();
    }
}


void updateMachineState() {
    // pinState = digitalRead(RELAY_PIN);        // Actual machine state
    // pinStateAuto = digitalRead(RELAY_PIN4);

    pinMode(pin5, INPUT); //auto run 
    pinMode(pin4, INPUT); //mould open end

    pinState = digitalRead(pin5);        // Actual machine state
    pinStateAuto = digitalRead(pin4);

    static int lastPinState = HIGH;                // Track cycle signal
    static int lastPinStateAuto = HIGH;            // Track auto/manual switch

    // Handle force stop
    if (forceTimerStop) {
        if (currentState == RUNNING) {
            stopCycleTimer("forced_stop");
        }
        currentState = IDLE;
        return;
    }

    // Handle auto/manual switch (pinStateAuto)
    if (pinStateAuto != lastPinStateAuto) {
        if (pinStateAuto == HIGH) {
            // Auto -> Manual
            Serial.println("Switched to Manual Mode");
            if (currentState == RUNNING) {
                stopCycleTimer("abnormal_cycle");  // Stop cycle immediately
            }
            startDowntimeTimer();
        } else {
            // Manual -> Auto
            Serial.println("Switched to Auto Mode");
            stopDowntimeTimer();
        }
        lastPinStateAuto = pinStateAuto;  // Update for next check
    }

    // Handle normal cycle transitions when in Auto mode
    if (pinStateAuto == LOW) {
      if (pinState != lastPinState) {
          Serial.print("Cycle Signal changed to: ");
          Serial.println(pinState == LOW ? "HIGH" : "LOW");

          if (lastPinState == LOW) {
              Serial.println("Timer Continue!");
          } else {
              stopCycleTimer("normal_cycle");
              startCycleTimer();
          }

          lastPinState = pinState; 
    }
  }

}

// --------------------- Cycle Timer Functions ---------------------
void startCycleTimer() {
    if (blockNewCycles) {
        Serial.println("New cycles blocked due to pending reboot.");
        return;
    }

    startTime = millis();
    currentState = RUNNING;
    Serial.println("Normal Cycle Timer Started...");
}

void stopCycleTimer(const char* reason) {
    if (currentState == RUNNING) {
        float elapsedTime = (millis() - startTime) / 1000.0;
        Serial.print("Cycle Timer Stopped - Reason: ");
        Serial.println(reason);
        Serial.print("Elapsed Time: ");
        Serial.println(elapsedTime);
        isTimerRunning = false;

        sendElapsedTimeMP(elapsedTime, reason);
        currentState = IDLE;
    }
}

void restart_esp(){
  String payload = "{ \"machine_id\": \"" + String(machine_id) + "\" }";  // Ensure correct JSON format
  // machine_id 
  status = true;
  if (mqttClient.connected()) {
      mqttClient.publish("action/get_mpid", payload.c_str());
      Serial.print("MQTT Message sent: ");
      Serial.println(payload);
  } else {
      Serial.println("MQTT not connected, cannot publish message.");
  }
}

// --------------------- Downtime Timer Functions ---------------------
void startDowntimeTimer() {
    if (!isDowntimeTimerRunning) {
        downtimeStart = millis();
        isDowntimeTimerRunning = true;
        Serial.println("Downtime Timer Started...");
    }
}

void stopDowntimeTimer() {
    if (isDowntimeTimerRunning) {
        float downtimeElapsed = (millis() - downtimeStart) / 1000.0;
        Serial.print("Downtime Timer Stopped. Total downtime: ");
        Serial.print(downtimeElapsed);
        Serial.println(" seconds");

        sendElapsedTimeMP(downtimeElapsed, "downtime");
        isDowntimeTimerRunning = false;
    }
}

// --------------------- Downtime Timer Check (Call in Loop) ---------------------
void checkDowntimeTimer() {
    if (isDowntimeTimerRunning) {
        unsigned long currentDowntime = millis() - downtimeStart;
        if (currentDowntime >= MAX_DOWNTIME_MS) {
            Serial.println("Downtime exceeded 15 minutes! Stopping logging...");
            stopLoggingOveride();
            isDowntimeTimerRunning = false;  // Optional: stop the downtime timer after stopping logging
        }
    }
}




////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////



/** Function to Connect to WiFi */
void connectWiFi() {
    Serial.print("Connecting to WiFi...");
    WiFi.begin(ssid, password);
    int attempts = 0;
    
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi Connected!");
        Serial.print("IP Address: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("\nWiFi Connection Failed!");
    }
}

/** Function to Check and Reconnect WiFi */
void checkWiFiReconnect() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi Disconnected! Reconnecting...");
        WiFi.disconnect(); // Only if you want to reset the connection fully
        WiFi.reconnect();

        int retries = 0;
        while (WiFi.status() != WL_CONNECTED && retries < 10) {
            delay(500);
            Serial.print(".");
            retries++;
        }

        if (retries >= 10) {
            Serial.println("\nWiFi Reconnect Failed! Restarting...");
            // ESP.restart();  // Ensure semicolon is present
        } else {
            Serial.println("\nWiFi Reconnected!");
        }
    }
}


void connectMQTT() {
    while (!mqttClient.connected()) {
        Serial.print("Attempting MQTT connection...");

        // Construct the Last Will and Testament (LWT) message properly
        String payload_off = "{\"status\": \"disconnected\", \"machineid\": \"" + String(machine_id) + "\"}";
        #
        // Convert to a C-string (char array) for MQTT compatibility
        const char* lwt_message = payload_off.c_str();

        // Attempt to connect with LWT
        if (mqttClient.connect(client_id, topic_status, 1, true, lwt_message)) {
            Serial.println("Connected!");
            mqttClient.subscribe(status_topic.c_str());


            // Send a status update after successful connection
            String payload_on = "{\"status\": \"connected\", \"machineid\": \"" + String(machine_id) + "\"}";
            mqttClient.publish(topic_status, payload_on.c_str(), true);
        } else {
            Serial.println("Failed. Retrying in 5s...");
            delay(5000);
        }
    }
}

/** Function to Check and Reconnect MQTT */
void checkMQTTReconnect() {
    if (!mqttClient.connected()) {
        connectMQTT();
    }
}



// MQTT callback function
void callback(char* topic, byte* payload, unsigned int length) {
    Serial.print("Message received on topic: ");
    Serial.println(topic);

    // Prevent buffer overflow
    char json[256];
    if (length >= sizeof(json)) {
        Serial.println("Payload too large, truncating...");
        length = sizeof(json) - 1;
    }
    memcpy(json, payload, length);
    json[length] = '\0';

    // Deserialize JSON
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, json);

    if (error) {
        Serial.print("JSON Deserialization failed: ");
        Serial.println(error.c_str());
        return;
    }

    // Ensure the "command" key exists
    if (!doc.containsKey("command")) {
        Serial.println("Missing 'command' key in JSON!");
        return;
    }

    const char* command = doc["command"];
    
    // Prevent null-pointer crash on strcmp
    if (command == nullptr) {
        Serial.println("Command is NULL, ignoring message.");
        return;
    }

    // Retrieve other keys safely
    if (doc.containsKey("mp_id")) {
        mp_id = doc["mp_id"];
    } else {
        Serial.println("Missing 'mp_id' key in JSON!");
    }

    if (doc.containsKey("main_id")) {
        main_id = doc["main_id"];
    } else {
        Serial.println("Missing 'main_id' key in JSON!");
    }

    if (doc.containsKey("mould_id")) {
        mould_id = doc["mould_id"].as<String>();
    }

    Serial.println("Received JSON Message:");
    Serial.println(command);
    Serial.println(main_id);

    // Execute the command
    if (strcmp(command, "start") == 0) {
        startLogging();
    } else if (strcmp(command, "stop") == 0) {
        stopLogging();
    } else if (strcmp(command, "ums") == 0) {
        ums();
    } else if (strcmp(command, "ume") == 0) {
        ume();
    } else if (strcmp(command, "qas") == 0) {
        qas();
    } else if (strcmp(command, "qae") == 0) {
        qae();
    } else if (strcmp(command, "dms") == 0) {
        dms();
    } else if (strcmp(command, "dme") == 0) {
        dme();
    } else if (strcmp(command, "true") == 0) {
        status = true;
    } else {
        Serial.println("Unknown command received.");
    }
}


// Function to publish elapsed time to MQTT
void sendElapsedTime(float time, const String& action) {
  String payload = "{ \"elapsed_time_ms\": " + String(time) +
                  //  ", \"type\": \"cycle_time\"" + 
                   ", \"main_id\": \"" + main_id + "\"" +
                  //  ", \"mp_id\": \"" + mp_id + "\"" + 
                   ", \"mould_id\": \"" + mould_id + "\"" +  
                   ", \"action\": \"" + action + "\"" +  // Ensure action is in quotes
                   ", \"machineid\": \"A1\" }";

  mqttClient.publish("machine/cycle_time", payload.c_str());
  Serial.print("MQTT Message sent: ");
  Serial.println(payload);
}

void sendElapsedTimeMP(float time, const String& action) {
  String payload = "{ \"elapsed_time_ms\": " + String(time) +
                  //  ", \"type\": \"cycle_time\"" + 
                   ", \"main_id\": \"" + main_id + "\"" +
                   ", \"mp_id\": \"" + mp_id + "\"" + 
                   ", \"mould_id\": \"" + mould_id + "\"" +  
                   ", \"action\": \"" + action + "\"" +  // Ensure action is in quotes
                   ", \"machineid\": \"A1\" }";

  mqttClient.publish("machine/cycle_time", payload.c_str());
  Serial.print("MQTT Message sent: ");
  Serial.println(payload);
}

 /*
 so now if command received = ums 
 start function ums
 until command ume is received 
 stop timer and insert query into mysql
  */ 

void ums() {
  if (!isTimerRunning) {
    startTime = millis();
    isTimerRunning = true;
    Serial.println("Timer Started");
    Serial.println("Up mould progress has started");
  } else {
    Serial.println("Timer is already running!");
  }
}

void ume() {
  if (isTimerRunning) {
    float elapsedTime = ((millis() - startTime) / 1000.0); // Convert to seconds
    isTimerRunning = false; // Reset the flag

    String action = "up mould"; // Declare action as a String
    Serial.println("Timer Stopped!");
    Serial.print("Elapsed Time: ");
    Serial.println(elapsedTime);

    sendElapsedTime(elapsedTime, action); // Send the elapsed time via MQTT or other method
  } else {
    Serial.println("Up mould progress has not started yet");
  }
}

void qas(){
  if (!isTimerRunning) {
    startTime = millis();
    isTimerRunning = true;
    Serial.println("Timer Started");
    Serial.println("Adjustment/QA-QC progress has started");
  } else {
    Serial.println("Timer is already running!");
  }
}

void qae(){
  if (isTimerRunning) {
    float elapsedTime = ((millis() - startTime) / 1000.0); // Convert to seconds
    isTimerRunning = false; // Reset the flag

    String action = "adjustment/QA-QC"; // Declare action as a String
    Serial.println("Timer Stopped!");
    Serial.print("Elapsed Time: ");
    Serial.println(elapsedTime);

    sendElapsedTime(elapsedTime, action); // Send the elapsed time via MQTT or other method
  } else {
    Serial.println("Adjustment/QA-Q progress has not started yet");
  }
}

void dms(){
  if (!isTimerRunning) {
    startTime = millis();
    isTimerRunning = true;
    Serial.println("Timer Started");
    Serial.println("Down Mould progress has started");
  } else {
    Serial.println("Timer is already running!");
  }
}

void dme(){
  if (isTimerRunning) {
    float elapsedTime = ((millis() - startTime) / 1000.0); // Convert to seconds
    isTimerRunning = false; // Reset the flag

    String action = "down mould"; // Declare action as a String
    Serial.println("Timer Stopped!");
    Serial.print("Elapsed Time: ");
    Serial.println(elapsedTime);

    sendElapsedTime(elapsedTime, action); // Send the elapsed time via MQTT or other method
  } else {
    Serial.println("Down Mould progress has not started yet");
  }
}

void startLogging() {

  Serial.println("Start logging");   // Log to the Serial Monitor
  status = true;   // Update the status
  digitalWrite(2, HIGH);  
  delay(1000);
  digitalWrite(2, LOW);  

}

void stopLogging() {
  Serial.println(F("Stop logging"));   // Save RAM by using the F() macro
  status = false;

  isTimerRunning = false;
  digitalWrite(2, HIGH);  // Turn on the LED on ESP32
  delay(1000);
  digitalWrite(2, LOW);   // Turn off the LED after 1 second

  String payload = "{ \"mp_id\": \"" + String(mp_id) + "\" }";  // Ensure correct JSON format
  // machine_id 
  if (mqttClient.connected()) {
      mqttClient.publish("action/job_end", payload.c_str());
      Serial.print("MQTT Message sent: ");
      Serial.println(payload);
  } else {
      Serial.println("MQTT not connected, cannot publish message.");
  }
}


void stopLoggingOveride() {
  Serial.println(F("Stop logging"));   // Save RAM by using the F() macro
  status = false;
  hasTimedOut = true;

  isTimerRunning = false;
  digitalWrite(2, HIGH);  // Turn on the LED on ESP32
  delay(1000);
  digitalWrite(2, LOW);   // Turn off the LED after 1 second

  String payload = "{ \"machine_id\": \"" + String(machine_id) + "\" }";  // Ensure correct JSON format
  // machine_id 
  if (mqttClient.connected()) {
      mqttClient.publish("overide/off", payload.c_str());
      Serial.print("MQTT Message sent: ");
      Serial.println(payload);
  } else {
      Serial.println("MQTT not connected, cannot publish message.");
  }
}

// when only log then timeout = false, this signal will keep bring true until auto run signal is high/manual on?

