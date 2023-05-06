#include <DHT.h>
#include <MQ135.h>

#include <ArduinoJson.h>
#include <ArduinoJson.hpp>

#include "WiFiNINA.h"
#include <ArduinoMqttClient.h>

#include <Servo.h>
#include "arduino_secrets.h"

#define DHTPIN 2  //D2 pin
#define DHTTYPE DHT22
#define MQPIN A2

char ssid[] = SECRET_SSID;
char pass[] = SECRET_PASS; 


WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);

const char broker[] = SECRET_BROKER_IP;
int port = 1883;
const char broker_username[] = SECRET_BROKER_USERNAME;
const char broker_password[] = SECRET_BROKER_PASSWORD;
const char pub_topic[] = "project/arduino/readings";
const char sub_topic[] = "project/arduino/get";

// 5 second interval because the dht22 sensor is slow and takes time to return readings and
// we dont wanna send data so frequently either
const long interval = 2000;
unsigned long previousMillis = 0;
int count = 0;
// declaring dht sensor and json payload
DHT dht(DHTPIN, DHTTYPE);
MQ135 mq135_sensor(MQPIN);
/*
  Sub to the same topic and send the info whenever the ping is recieved
  Or use another topic to recieve the ping
*/
// Json Payload to send: {dht22: [temp, humidity, timestamp], mq135: [ppm levels]}

Servo windowController;

// close angle
int windowOpen = 160;
// starting position, at 60 the shaft is parallel to the body
int windowClose = 60;
// intialliy keep window close
int windowPos = windowClose;
bool windowAuto = true;

void reconnect() {
  while (!mqttClient.connected()) {
    if (!mqttClient.connect(broker, port)) {  
      Serial.print("MQTT connection failed! Error code = ");
      Serial.println(mqttClient.connectError());
      Serial.println("Retrying...");
    }
  }
  // If successfully connected, alert the user
  Serial.println("You're conneted to MQTT broker!");
  Serial.println();
  // add subscription for window controll event
  mqttClient.subscribe(sub_topic);
  
  Serial.print("Subbing to!");
  Serial.println(sub_topic);
  Serial.println();
}

void setup() {
  Serial.begin(9600);
  while (!Serial);
  
  // while the status is "not connected" keep trying  
  while (WiFi.begin(ssid, pass) != WL_CONNECTED) {
    Serial.print("Attempting to connect to network: ");
    Serial.println(ssid);
    
    // wait 10 seconds for the connection
    delay(10000);
  }
  
  Serial.println("You're connected to the network");
  Serial.println("-------------------------------");
  
  mqttClient.setId("Ahbar_ArduinoIOT33");
  mqttClient.setUsernamePassword(broker_username, broker_password);
  
  reconnect();

  // DHT
  dht.begin();
  windowController.attach(3);
  windowController.write(windowPos);
  delay(1000);
}

void loop() {
  // polling basically allows the client to keep the connection alive 
  // mqttClient.poll();
  if (!mqttClient.connected()) {
    Serial.println("MQTT Client disconnected.. reconnecting... please wait!");
    reconnect();
  }

  int messageSize = mqttClient.parseMessage();
  
  if (messageSize) {
      // we received a message, print out the topic and contents
      Serial.print("Received a message with topic '");
      Serial.print(mqttClient.messageTopic());
      Serial.print("', length ");
      Serial.print(messageSize);
      Serial.println(" bytes:");

      StaticJsonDocument<256> doc;
      deserializeJson(doc, mqttClient);
      Serial.print(doc.as<String>());
      
      if (doc["window"] == 2) {
        windowAuto = !windowAuto;
      } else if (doc["window"] == 0) {
        windowPos = windowClose;
      } else {
        windowPos = windowOpen;
      }
      windowController.write(windowPos);
      
      Serial.print("Window auto controller mode enabled: ");
      Serial.println(windowAuto);

      Serial.println();
      Serial.println();
  }
  
  unsigned long currentMillis = millis();
  
  if (currentMillis - previousMillis >= interval) {
    // update the variable 
    previousMillis = currentMillis;
    
    // get sensor readings
    // get humidity
    float humidity = dht.readHumidity();
    // get temperature reading in celsius
    float temp = dht.readTemperature();
    float correctedPPM = mq135_sensor.getCorrectedPPM(temp, humidity);
    
    if (windowAuto && temp >= 30 && windowPos != windowOpen) {
      Serial.println("TOO HOT!! Open the windows!");
      windowPos = windowOpen;
      windowController.write(windowPos);
      delay(1000);
    } else if (windowAuto && temp <= 25 && windowPos != windowClose) {
      Serial.println("TOO COLD!! Close the windows!");
      windowPos = windowClose;
      windowController.write(windowPos);
      delay(1000);
    }
      
    // json payload to be sent 
    DynamicJsonDocument doc(1024);
    
    doc["sensor"] = "DHT22 and MQ135";
    doc["timestamp"] = "NA"; // need to get an rtl sensor or maybe can use an api to get the data 
    doc["temp"] = temp;
    doc["humidity"] = humidity;
    doc["PPM level"] = correctedPPM;
    // serializeJson(doc, Serial);
    
    // print the information about the message and topic
    Serial.print("Sending message to the topic: ");
    Serial.println(pub_topic);
    char payload[1028]; 
    serializeJson(doc, payload);
    Serial.println(payload);
    
    // now sending the message
    // The print interface can be used to set the message contents
    mqttClient.beginMessage(pub_topic);
    // mqttClient.print("Hello from Ahbar's arduino");
    // mqttClient.print(count);
    
    mqttClient.print(payload);
    mqttClient.endMessage(); 
    
    Serial.print("Current Window Pos:");
    Serial.println(windowPos);
    Serial.println();
      
    count++;
  }
}