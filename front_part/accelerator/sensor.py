import Adafruit_MCP3008
import Adafruit_GPIO.GPIO as AGPIO
import RPi.GPIO as RPI
from AbstractClasses import AbstractSensor

class AcceleratorSensor(AbstractSensor):
    def __init__(self, channel=0, clk=21, cs=7, miso=19, mosi=20, verbose=False):
        self.verbose = verbose
        self.channel = channel
        
        # Numérotation BCM pour les pin 21/20/19/7
        RPI.setmode(RPI.BCM)
        gpio = AGPIO.RPiGPIOAdapter(RPI)
        #Bit-bang sur les GPIO
        self.mcp = Adafruit_MCP3008.MCP3008(clk=clk, cs=cs, miso=miso, mosi=mosi, gpio=gpio)
        self.lastAccelPedal = None

    def read(self):
        value = int(self.mcp.read_adc(self.channel))
        self._print(f"Raw accelerator value: {value}")
        return value

    def clamp_acceleration(self, value, minVal=250, maxVal=875):
        clamped = max(minVal, min(value, maxVal))
        self._print(f"Clamped value: {clamped}")
        return clamped

    def map_to_output(self, value, inMin=250, inMax=875, outMax=1023):
        mapped = int(((value - inMin) / (inMax - inMin)) * outMax)
        self._print(f"Mapped value: {mapped}")
        return mapped

    def has_changed(self, value, threshold=0):
        if self.lastAccelPedal is None or abs(value - self.lastAccelPedal) > threshold:
            self.lastAccelPedal = value
            self._print(f"Value changed: {value}")
            return True
        return False

    def _print(self, *args, **kwargs):
        if self.verbose:
            print("[SENSOR ACCELERATOR]",*args, **kwargs)
