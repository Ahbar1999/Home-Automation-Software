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
const long interval = 5000;
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
int windowPos = 0;

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
  windowController.attach(3);
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
    float correctedPPM = mq135_sensor.getCorrectedPPM(temp, humidity);
    
    if (temp >= 30 && windowPos < 90) {
      Serial.println("TOO HOT!! Open the windows!");
      windowPos = 90;
      windowController.write(windowPos);
      delay(500);
    } else if (temp < 30 && windowPos > 0) {
      Serial.println("TOO COLD!! Close the windows!");
      windowPos = 0;
      windowController.write(windowPos);
      delay(500);
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
