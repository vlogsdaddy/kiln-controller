# Max Vin to Rasp pin2
# Max GND to Rasp pin6
# Max DO to Rasp pin21
# Max CS to Rasp pin15
# Max CLK to Rasp pin23

import time
import board
import digitalio
import adafruit_max31855

# Set up SPI bus
spi = board.SPI()
cs = digitalio.DigitalInOut(board.D22)  # CS (Chip Select) connected to GPIO 22

# Create MAX31855 object
thermocouple = adafruit_max31855.MAX31855(spi, cs)

# Test loop to print temperature every second
while True:
    try:
        # Get temperature in Celsius
        temperature_c = thermocouple.temperature
        print(f"Temperature: {temperature_c:.2f} °C")
        time.sleep(1)  # Wait 1 second before reading again
    except Exception as e:
        print(f"Error reading temperature: {e}")
        time.sleep(1)
