import time
import board
import digitalio
import adafruit_max31855

# Thermocouple setup (using MAX31855 as example)
spi = board.SPI()
cs = digitalio.DigitalInOut(board.D22)
thermocouple = adafruit_max31855.MAX31855(spi, cs)

while True:
    temperature = thermocouple.temperature
    print(f"Temperature: {temperature} °C")
    time.sleep(1)
