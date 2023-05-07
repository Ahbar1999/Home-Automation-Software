from umqtt.simple import MQTTClient, MQTTException
import network, utime, machine, json

BROKER_ADDR = "139.59.61.26"
client = MQTTClient("esp_32_umqtt_client", BROKER_ADDR, user='ahbar', password='1234', keepalive=600, port='1883')
sta_if = network.WLAN(network.STA_IF)
    
def do_connect(SSID, PASSWORD):
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        sta_if.connect(SSID, PASSWORD)
        while not sta_if.isconnected():
            pass
    print('network config:', sta_if.ifconfig())
    
    # connect to our broker on cloud
    try:
        client.connect()
    except MQTTException as e:
        print("Connection to the broker failed!")
        print("MQTTException Error code: ", e)

do_connect('OnePlus 7 Pro', '12345678')
# do_connect('OnePlus 7 Pro', '12345678')

pins = {}
led1 = machine.Pin(2, machine.Pin.OUT)
led2 = machine.Pin(15, machine.Pin.OUT)
led3 = machine.Pin(22, machine.Pin.OUT)
led4 = machine.Pin(23, machine.Pin.OUT)

pins['bulb 1'] = led1
pins['bulb 2'] = led2
# this should be the duty cycle pin
pins['fan'] = led3
pins['AC'] = led4

APP_TOPIC = b'project/esp32/appliances'
STATUS_TOPIC = b'project/esp32/appliances/status'
WIFI_TOPIC = b'project/wifi_details/set'

#----------PIR SETUP----------------#
sensor_pir = machine.Pin(4, machine.Pin.IN)
buzzer=  machine.Pin(5, machine.Pin.OUT)

def pir_handler(pin):
    print("ATTENTION! Motion detected!")
    i = 4
    start = utime.ticks_ms()
    buzzer.value(1)
    while i >= 0:
        curr = utime.ticks_ms()
        print(i, curr, start, utime.ticks_diff(curr, start))
        if utime.ticks_diff(curr, start) >= 500:
            if buzzer.value() == 0:
                buzzer.value(1)
            else:
                buzzer.value(0)
            i -= 1
            start = curr
    buzzer.value(0)
    
sensor_pir.irq(trigger=machine.Pin.IRQ_RISING, handler=pir_handler)

def handle_message(topic, msg):
    print("message recieved from broker")
    print(topic, msg)
    if topic == APP_TOPIC:
        handle_op(topic, msg)
    elif topic == STATUS_TOPIC:
        if not json.loads(msg.decode()):
            print("sending back pin status")
            client.publish(STATUS_TOPIC, json.dumps(get_pin_status()))
    elif topic == WIFI_TOPIC:
        wifi_details = json.loads(msg.decode())
        if wifi_details['ssid'] is not "None":
            # disconnect mqtt client
            client.disconnect()
            # utime.sleep(1)
            # disconnect wifi
            sta_if.disconnect()
            while sta_if.isconnected():
                # wait for the microcontroller to disconnect
                # it takes time
                pass
            do_connect(wifi_details['ssid'], wifi_details['password'])
    # elif ... other topics and their handling
    
def handle_op(topic, msg):
    # print("blinking led")
    m = json.loads(msg.decode())
    # print(m)
    for pin in pins:
        # print(pin, pins[pin].value())
        print(m.get(pin))
        if m.get(pin) is not None:
            pins[pin].value(int(m[pin]))
    print("sending back pin status")     
    client.publish(STATUS_TOPIC, json.dumps(get_pin_status()))
    '''
    if m['led'] == '1':
    #if msg.decode() == '1':
        led.value(1)
    else:
        led.value(0)
    '''
client.set_callback(handle_message)
# subscribe to the LED on the broker
client.subscribe(APP_TOPIC)
# client.subscribe(STATUS_TOPIC)
client.subscribe(WIFI_TOPIC)

def get_pin_status():
    d = {}
    for pin in pins:
        d[pin] = str(pins[pin].value())
    print(d)
    return d

start = utime.ticks_ms()
while True:
    # print('pinging broker')
    # client.ping()
    curr = utime.ticks_ms()
    if utime.ticks_diff(curr, start) / 1000 > 2:
        client.publish(STATUS_TOPIC, json.dumps(get_pin_status()))
        start = curr
    client.check_msg()
    # utime.sleep_ms(500)

client.disconnect()

