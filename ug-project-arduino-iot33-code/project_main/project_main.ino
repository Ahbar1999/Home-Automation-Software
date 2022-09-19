#include "arduino_secrets.h"
#include <DHT.h>

#include <ArduinoJson.h>
#include <ArduinoJson.hpp>

#include "WiFiNINA.h"
#include <ArduinoMqttClient.h>

#define DHTPIN 2  //D2 pin
#define DHTTYPE DHT22


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
const long interval = 5000;
unsigned long previousMillis = 0;
int count = 0;
// declaring dht sensor and json payload
DHT dht(DHTPIN, DHTTYPE);


/*
  Sub to the same topic and send the info whenever the ping is recieved
  Or use another topic to recieve the ping
*/
// Json Payload to send: [temp, humidity, timestamp]

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
  
  if (!mqttClient.connect(broker, port)) {
    Serial.print("MQTT connection failed! Error code = ");
    Serial.println(mqttClient.connectError());
    
    // go into infinite loop
    // basically so the console does not close itself and user can do that
    while (1);
  }
  
  // If successfully connected, alert the user
  Serial.println("You're conneted to MQTT broker!");
  Serial.println();

  // DHT
  dht.begin();
}

void loop() {
  // polling basically allows the client to keep the connection alive 
  mqttClient.poll();
  
  unsigned long currentMillis = millis();
  
  if (currentMillis - previousMillis >= interval) {
    // update the variable 
    previousMillis = currentMillis;
    
    // get sensor readings
    // get humidity
    float humidity = dht.readHumidity();
    // get temperature reading in celsius
    float temp = dht.readTemperature();
    
    // json payload to be sent 
    DynamicJsonDocument doc(1024);
    
    doc["sensor"] = "DHT22";
    doc["timestamp"] = "NA"; // need to get an rtl sensor or maybe can use an api to get the data 
    doc["temp"] = temp;
    doc["humidity"] = humidity;
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
    
    Serial.println();
    
    count++;
  }
  
}