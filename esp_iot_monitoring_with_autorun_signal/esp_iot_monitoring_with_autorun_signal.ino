#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

#define RELAY_PIN 2
#define RELAY_PIN5 4

const char *ssid = "udsb-nova";     // Your WiFi SSID
const char *password = "udsb2735***"; // Your WiFi password
const char* mqtt_server = "192.168.5.31"; // Host machine IP
// const char* mqtt_server = "192.168.1.17"; // Host machine IP
// const char* mqtt_server = " 192.168.132.192"; // Host machine IP
const int mqtt_port = 1883;

float startTime = 0;  // To store the start time
float elapsedTime = 0; // To store the elapsed time
bool isTimerRunning = false;   // Flag to track if the timer is running
bool lastState = LOW;  // Track last signal state
const int pin5 = 5;         // Pin to monitor
const int pin4 = 4;         // Pin to monitor

const int pinled = 2;

const char* mqtt_topic = "machine/checking"; // The topic you want to subscribe to
const char* mqtt_topic_ums = "machine/ums"; // The topic you want to subscribe to

const char* machine_id = "A1";   // Machine-specific identifier
String client_id_str = "ESP_" + String(machine_id);
char client_id[20];  // Fixed-size buffer for client ID

String status_topic = "machines/" + String(machine_id);  // MQTT topic

const char* topic_status = "status/A1";   // Status topic- Send esp status to python and update status of esp in database


int mp_id = -1;
int main_id = -1;
String mould_id = "";
bool status = false;

WiFiServer server(80);
WiFiClient espClient;
PubSubClient mqttClient(espClient);

void connectMQTT() {
    while (!mqttClient.connected()) {
        Serial.print("Attempting MQTT connection...");

        // Construct the Last Will and Testament (LWT) message properly
        String payload_off = "{\"status\": \"disconnected\", \"machineid\": \"" + String(machine_id) + "\"}";
        
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


void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);

    pinMode(pinled, OUTPUT);
    // pinMode(pin5, INPUT);
    pinMode(RELAY_PIN, INPUT_PULLDOWN);  // Enable internal pulldown
    pinMode(RELAY_PIN5, INPUT_PULLDOWN);  // Enable internal pulldown
    digitalWrite(pinled, LOW);
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

//new function 
//if pin 6 high send message to python side to let them know to mass prob has start
//when pin6 high run function start logging and vice versa
//let pin6 be status i guess, if not pin 6 dont run, if pin 6 status = true start logging
// so i need it to still log data when the auto run pin is off
// the auto run needs to be checked once per batch
// so like if pin = high, first time = false
// then when does it restart



void loop() {
    if (!mqttClient.connected()) {
        connectMQTT();
    }
    mqttClient.loop();  // Process MQTT messages

    int pinState = digitalRead(RELAY_PIN5);  // Read pin 5 state
    int pinStateAuto = digitalRead(RELAY_PIN);  // Read pin 2 state
    delay(50);  // Small delay to filter noise
    status = (pinStateAuto == HIGH);

    if (status) {
        if (pinState != lastState) {  // Detect a signal change
            Serial.print("Signal changed to: ");
            Serial.println(pinState == LOW ? "HIGH" : "LOW");

            if (lastState == HIGH) {  
                // Last was LOW → New HIGH detected → Start timer
                // startTime = millis();
                // isTimerRunning = true;
                Serial.println("Timer Continue!");
                digitalWrite(pinled, HIGH);  // Turn on LED indicator
            } else {  
                // Last was HIGH → New LOW detected → Stop and record time
                float elapsedTime = (millis() - startTime) / 1000.0;  // Convert to seconds
                isTimerRunning = false;
                Serial.println("Timer Stopped!");
                Serial.print("Elapsed Time: ");
                Serial.print(elapsedTime);
                Serial.println(" seconds");
                digitalWrite(pinled, LOW);  // Turn off LED indicator

                // Send elapsed time over MQTT
              if (pinStateAuto == HIGH){
                sendElapsedTimeMP(elapsedTime, "normal_cycle");
              } else{
                sendElapsedTimeMP(elapsedTime, "abnormal_cycle");
              }

                // Restart timer immediately
                startTime = millis();
                isTimerRunning = true;
                Serial.println("Timer Restarted...");
                digitalWrite(pinled, HIGH);  // Turn LED back on
                // startTime = millis();
                // isTimerRunning = true;
            }

            lastState = pinState;  // Update last signal state   
        }
    } else {
        if (pinState != lastState) {  // Detect a signal change
            Serial.print("Signal changed to: ");
            Serial.println(pinState == LOW ? "HIGH" : "LOW");

            if (lastState == HIGH) {  
                // Last was LOW → New HIGH detected → Start timer
                // startTime = millis();
                // isTimerRunning = true;
                Serial.println("Timer Continue!");
                digitalWrite(pinled, HIGH);  // Turn on LED indicator
            } else {  
                // Last was HIGH → New LOW detected → Stop and record time
                float elapsedTime = (millis() - startTime) / 1000.0;  // Convert to seconds
                isTimerRunning = false;
                Serial.println("Timer Stopped!");
                Serial.print("Elapsed Time: ");
                Serial.print(elapsedTime);
                Serial.println(" seconds");
                digitalWrite(pinled, LOW);  // Turn off LED indicator

                // Send elapsed time over MQTT
              if (pinStateAuto == HIGH){
                sendElapsedTimeMP(elapsedTime, "normal_cycle");
              } else{
                sendElapsedTimeMP(elapsedTime, "abnormal_cycle");
              }

                // Restart timer immediately
                startTime = millis();
                isTimerRunning = true;
                Serial.println("Timer Restarted...");
                digitalWrite(pinled, HIGH);  // Turn LED back on
                // startTime = millis();
                // isTimerRunning = true;
            }

            lastState = pinState;  // Update last signal state
        }
    }
}




// void loop() {
//   if (!mqttClient.connected()) {
//         connectMQTT();
//     }
//   mqttClient.loop();  // Process MQTT messages

// int pinState = digitalRead(pin5);  // Read the state of pin 5

// if (status) {
//   // If pin 5 goes HIGH and the timer is not already running, start the timer
//   if (pinState == LOW && !isTimerRunning) {
//     startTime = millis();  // Record the current time
//     isTimerRunning = true; // Set timer running flag
//     Serial.println("Timer Started");
//     digitalWrite(pinled, HIGH); // Turn on LED as a visual indicator
//   }

//   // If pin 5 goes LOW and the timer is running, stop the timer
//   if (pinState == HIGH && isTimerRunning) {
//     float elapsedTime = ((millis() - startTime) / 1000.0); // Calculate elapsed time in seconds
//     isTimerRunning = false;  // Reset timer running flag
//     Serial.println("Timer Stopped!");
//     Serial.print("Elapsed Time: ");
//     Serial.print(elapsedTime);
//     Serial.println(" seconds");
//     digitalWrite(pinled, LOW);  // Turn off LED as a visual indicator

//     // Send elapsed time over MQTT or process it further
//     sendElapsedTimeMP(elapsedTime, "normal_cycle");
//   }
// } else {
//   // Serial.println("Machine status not on");
// }

// // Add a small delay to avoid rapid state changes
// delay(100);  // Reduced delay for smoother operation

// }





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

  if (mqttClient.connected()) {
      mqttClient.publish("action/job_end", payload.c_str());
      Serial.print("MQTT Message sent: ");
      Serial.println(payload);
  } else {
      Serial.println("MQTT not connected, cannot publish message.");
  }


}


