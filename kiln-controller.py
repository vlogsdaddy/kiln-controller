import time
import json
import board
import digitalio
import adafruit_max31855
import RPi.GPIO as GPIO
import requests
from simple_pid import PID
from bisect import bisect_left
from datetime import datetime

# Convert C to F
def c_to_f(c):
    return (c * 9/5) + 32

# Webhook setup
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

def send_slack_notification(time_str, target_temp_f, measured_temp_f):
    message = (
        f"🔥 Kiln Status Update 🔥\n"
        f"Time: {time_str}\n"
        f"Target Temp: {target_temp_f:.1f}°F\n"
        f"Measured Temp: {measured_temp_f:.1f}°F"
    )
    payload = {"text": message}
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Slack notification failed: {e}")

# Slack message setup
last_slack_time = 0
slack_interval = 30  # seconds

# GPIO setup
SSR_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(SSR_PIN, GPIO.OUT)

# Thermocouple setup (using MAX31855 as example)
spi = board.SPI()
cs = digitalio.DigitalInOut(board.D5)
thermocouple = adafruit_max31855.MAX31855(spi, cs)

# Load heating profile
with open('Test_firing.json') as f:
    profile = json.load(f)

# Convert profile into lookup lists
times = [p['time'] * 60 for p in profile]  # Convert minutes to seconds
temps = [p['temperature'] for p in profile]

# PID controller setup
pid = PID(5, 0.1, 1, setpoint=25)
pid.output_limits = (0, 1)  # Output between 0 (off) and 1 (on)

start_time = time.time()

log_file = open("kiln_log.txt", "a")  # Use "a" to append to the file
log_file.write("Time,TargetTemp_F,MeasuredTemp_F\n")

try:
    while True:
        elapsed = time.time() - start_time
        
        # Determine target temp based on time
        i = bisect_left(times, elapsed)
        if i == 0:
            target_temp = temps[0]
        elif i >= len(times):
            target_temp = temps[-1]
        else:
            # Interpolate
            t1, t2 = times[i-1], times[i]
            temp1, temp2 = temps[i-1], temps[i]
            frac = (elapsed - t1) / (t2 - t1)
            target_temp = temp1 + frac * (temp2 - temp1)

        pid.setpoint = target_temp

        # Read current temperature
        current_temp = thermocouple.temperature

        # Compute PID output
        output = pid(current_temp)

        # SSR control
        if output > 0.5:
            GPIO.output(SSR_PIN, GPIO.HIGH)
        else:
            GPIO.output(SSR_PIN, GPIO.LOW)

        # Send Slack notification
        if elapsed - last_slack_time > slack_interval:
            send_slack_notification(current_time_str, target_temp_f, measured_temp_f)
            last_slack_time = elapsed
        
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        measured_temp_f = c_to_f(current_temp)
        target_temp_f = c_to_f(target_temp)

        log_line = f"{current_time_str},{target_temp_f:.1f},{measured_temp_f:.1f}\n"
        log_file.write(log_line)
        log_file.flush()  # Ensure it's written to disk

        print(f"[{current_time_str}] Target: {target_temp_f:.1f}°F | Current: {measured_temp_f:.1f}°F | Output: {output:.2f}")

        time.sleep(1)

except KeyboardInterrupt:
    log_file.close()
    GPIO.cleanup()

