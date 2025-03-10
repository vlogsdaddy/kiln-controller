# kiln_controller

Pin Connections
1. Thermocouple (MAX31855) SPI Connection
VCC (MAX31855) → 3.3V (Raspberry Pi)
GND (MAX31855) → GND (Raspberry Pi)
CLK (MAX31855) → SCLK (Raspberry Pi, GPIO11, Pin 23)
CS (MAX31855) → GPIO5 (Pin 29) (As defined in the code, change if needed)
DO (MAX31855) → MISO (Raspberry Pi, GPIO9, Pin 21)
2. Solid State Relay (SSR) Connection
Relay Input + (Control Side) → GPIO6 (Pin 31) (As defined in the code, change if needed)
Relay Input - (Control Side) → GND (Raspberry Pi)
Relay Output (Load Side) → Kiln Power Circuit (Should be properly rated for your kiln's power requirements!)
3. Raspberry Pi Power
Ensure your Raspberry Pi is powered via the micro-USB or USB-C power adapter, depending on your model.
