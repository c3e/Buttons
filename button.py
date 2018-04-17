from neopixel import *
import RPi.GPIO as gpio
import os
import paramiko
import _thread
from time import sleep
from datetime import datetime
import math
#
# variables
#

LED_COUNT = 24     # Number of LED pixels.
LED_PIN = 18      # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 5       # DMA channel to use for generating signal (try 5)
LED_BRIGHTNESS = 64     # Set to 0 for darkest and 255 for brightest
LED_INVERT = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53
LED_STRIP = ws.WS2812_STRIP   # Strip type and colour ordering
door_pin = 22

#
# SSH Configs
#
SSH_LOG = 'ssh.log'
KNOWN_HOSTS = '~/buttond/known_hosts'
KEY_OBEN = '~/buttond/oben.key'
KEY_UNTEN = '~/buttond/id_rsa'

#
# GPIO Setup
#

gpio.setmode(gpio.BCM)

gpio.setup(door_pin, gpio.IN, pull_up_down=gpio.PUD_UP) 

gpio.setup(23, gpio.IN, pull_up_down = gpio.PUD_UP)
gpio.setup(17, gpio.IN, pull_up_down = gpio.PUD_UP)


#
# timinig
#

def millis(start_time):
    dt = datetime.now() - start_time
    ms = (dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds / 1000.0
    return ms

#
# Locking 
#

def ssh_state(host,name):
    err = "undef"
    paramiko.util.log_to_file(SSH_LOG) # sets up logging
    client = paramiko.SSHClient()
    client.load_host_keys(os.path.expanduser(KNOWN_HOSTS))
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pkey_file = open(os.path.expanduser(KEY_OBEN))
    pkey = paramiko.RSAKey.from_private_key(pkey_file)
    client.connect(host, username=name, pkey=pkey)

    sftp_client = client.open_sftp()
    remote_file = sftp_client.open('/tmp/door_state')
    content = remote_file.read()
    #print("SSH Out: ", content)
    if content == b'open':
        err =  "open"
    elif content == b'closed':
        err =  "closed"
    remote_file.close()
    sftp_client.close()
    client.close()
    return err

def threaded_get_states(bu,bo):
    while True:
        get_states(bu,bo)
        sleep(5)

def get_states(bu,bo):
    content = "undef"
    try:
        file = open("/tmp/door_state", "r")
        content = file.read()
        file.close()
    except:
        pass
    
    print("Unten: " , content)
    
    if content == "open":
        bu.set_state_locked(False)
    elif content == "closed":
        bu.set_state_locked(True)
    
    err = ssh_state("10.42.1.28", "pi")
    
    print("Oben: " , err )
    
    if err == "open":
        bo.set_state_locked(False)
    elif err == "closed":
        bo.set_state_locked(True)


def ssh(host, name):
    paramiko.util.log_to_file(SSH_LOG) # sets up logging
    client = paramiko.SSHClient()
    client.load_host_keys(os.path.expanduser(KNOWN_HOSTS))
    #client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pkey_file = open(os.path.expanduser(KEY_UNTEN))
    pkey = paramiko.RSAKey.from_private_key(pkey_file)
    client.connect(host, username=name, pkey=pkey)
    client.invoke_shell()
    sleep(2)
    client.close()

def lock(where):
    print ("locking!")
    if (where == "oben"):
        ssh("10.42.1.28", "close")
    if (where == "unten"):
        while (gpio.input(door_pin) != 0):
            sleep(1)
        ssh("10.42.1.20", "lock")


def unlock(where):
    print ("opening!")
    if (where == "oben"):
        ssh("10.42.1.28", "open")
    if (where == "unten"):
        if ( gpio.input(door_pin) == 0):
            ssh("10.42.1.20", "unlock")

#
# Button
#

def pulse_color(base_color, i):
    intensity = math.sin((i % 50) * math.pi / 50)
    r = int(base_color[0] * intensity)
    g = int(base_color[1] * intensity)
    b = int(base_color[2] * intensity)
    
    return Color(r, g, b)

class button:

    anim_onoff = False
    anim_state = 0
    lock_state = "undef"
    strip = ()
    leds = []
    led_gpio = 0
    button_gpio = 0
    lock_id = "none"
    timer_at = 0
    timer_a = 0

    def __init__(self, s_strip, s_leds, lock_id, gpio_button):
        self.strip = s_strip
        self.leds = s_leds
        self.lock_id = lock_id
        self.button_gpio = gpio_button

    def set_state_locked(self,locked):
        if locked is True:
            print("Set to Closed" )
            self.lock_state = "closed"
        else:
            print ("Set to Open")
            self.lock_state = "open"

    def setup_watcher():
        gpio.add_event_detect(self.gpio, gpio.FALLING, callback=button_press, bouncetime=350)

    def draw(self):
        if self.anim_onoff is True:
            self.anim()
        else:
            self.pulse()

    def anim(self):
        for l in self.leds:
            self.strip.setPixelColor(l, Color(255,255,255))
        self.strip.show()

    def pulse(self):
        self.anim_state = (self.anim_state+1)%100
        for l in self.leds:
            if self.lock_state == "open":
                self.strip.setPixelColor(l, pulse_color([0,255,0],self.anim_state))
            elif self.lock_state == "closed":
                foo = pulse_color([255,0,0],self.anim_state)
                self.strip.setPixelColor(l, foo)
                #self.strip.setPixelColor(l, Color( int(30 + math.sin(self.anim_state*math.pi/100) * 100 * 2), 0, 0))
            else:
                self.strip.setPixelColor(l, pulse_color([255,255,0],self.anim_state))
        self.strip.show()

    def button_press(self):
        if self.lock_state == "open":
            self.anim_onoff = True
            lock(self.lock_id)
            self.anim_onoff = False
        else:
            self.anim_onoff = True
            unlock(self.lock_id)
            self.anim_onoff = False
        return 0
    
    #
    # Button check must be run externally in loop if setup_watcher was not called
    #

    def check(self):
        if (gpio.input(self.button_gpio) == 0 and self.timer_a == 0) :
            self.timer_at = datetime.now()
            self.timer_a = 1
        if (gpio.input(self.button_gpio) == 1 and self.timer_a == 1):
            if millis(self.timer_at) > 200:
                _thread.start_new_thread(self.button_press, ())
            self.timer_a = 0

#
# Main Method
#

if __name__ == '__main__':
        strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, LED_STRIP)
        strip.begin()
        button_oben = button(strip, [0,1,2,3,4,5,6,7,8,9,10,11], "oben", 23 )
        button_unten = button(strip, [12,13,14,15,16,17,18,19,20,21,22,23], "unten", 17 ) 
        
        a = 0
        print ('End with ctrl-c')

        _thread.start_new_thread(threaded_get_states, (button_unten, button_oben) )
        while True:
            button_unten.draw()
            button_oben.draw()
            button_unten.check()
            button_oben.check()
            sleep(0.1)


