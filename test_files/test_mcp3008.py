import Adafruit_GPIO.SPI as SPI
import RPi.GPIO as RPI
import Adafruit_MCP3008 as MCP3008
import Adafruit_GPIO.GPIO as GPIO

RPI.setmode(RPI.BCM)
CLK,MISO,MOSI,CS = 21,19,20,7

gpio = GPIO.RPiGPIOAdapter(RPI)
mcp = MCP3008.MCP3008(clk=CLK,cs=CS,miso=MISO,mosi=MOSI,gpio=gpio)

try :
    while True:
        val = mcp.read_adc(0)
        print(val)
except KeyboardInterrupt:
    pass
finally:
    RPI.cleanup()
