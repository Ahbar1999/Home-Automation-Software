from umqtt.simple import MQTTClient, MQTTException
import network, utime, machine, json


def do_connect():
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        sta_if.connect('JioFiber-4G', 'auG1999w1fIp@$$w0rD')
        while not sta_if.isconnected():
            pass
    print('network config:', sta_if.ifconfig())


do_connect()


BROKER_ADDR = "139.59.61.26"
client = MQTTClient("esp_32_umqtt_client", BROKER_ADDR, user='ahbar', password='1234', keepalive=600, port='1883')
# connect to our broker on cloud
try:
    client.connect()
except MQTTException as e:
    print("Connection to the broker failed!")
    print("MQTTException Error code: ", e)
    
pins = {}
led = machine.Pin(2, machine.Pin.OUT)
pins['led'] = led
APP_TOPIC = b'project/esp32/appliances'
STATUS_TOPIC = b'project/esp32/appliances/status'


def handle_message(topic, msg):
    print("message recieved from broker")
    if topic == APP_TOPIC:
        blink_led(topic, msg)
        
    print("sending back pin status")
    client.publish(STATUS_TOPIC, json.dumps(get_pin_status()))
    # elif ... other topics and their handling

def blink_led(topic, msg):
    print("blinking led")
    m = json.loads(msg.decode())
    # print(type(m), m)
    if m['led'] == '1':
    #if msg.decode() == '1':
        led.value(1)
    else:
        led.value(0)

client.set_callback(handle_message)
# subscribe to the LED on the broker
client.subscribe(APP_TOPIC)

def get_pin_status():
    d = {}
    for pin in pins:
        d[pin] = str(pins[pin].value())
    # print(d)
    return d

while True:
    # print('pinging broker')
    # client.ping()
    # client.publish(STATUS_TOPIC, json.dumps(get_pin_status()))
    client.check_msg()
    # utime.sleep_ms(500)

client.disconnect()
