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

# Convert Celsius to Fahrenheit
def c_to_f(c):
    return (c * 9/5) + 32

# Slack webhook setup
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

# Slack status variables
last_slack_time = 0
slack_interval = 30  # seconds

# GPIO setup
SSR_PIN = 23
GPIO.setmode(GPIO.BCM)
GPIO.setup(SSR_PIN, GPIO.OUT)

# Thermocouple setup (using MAX31855)
spi = board.SPI()
cs = digitalio.DigitalInOut(board.D22)
thermocouple = adafruit_max31855.MAX31855(spi, cs)

# Load heating profile
with open('Test_cone6_glaze.json') as f:
    profile = json.load(f)

# Convert profile to lookup lists
times = [p['time'] * 60 for p in profile]  # minutes → seconds
temps = [p['temperature'] for p in profile]

# PID controller setup
pid = PID(5, 0.1, 1, setpoint=25)
pid.output_limits = (0, 1)  # 0 = off, 1 = full on

start_time = time.time()

log_file = open("kiln_log.txt", "a")
log_file.write("Time,TargetTemp_F,MeasuredTemp_F\n")

# Thermocouple error tracking
last_error_alert_time = 0
thermo_error_active = False
error_alert_interval = 10  # seconds

last_valid_temp = 25.0  # fallback default in °C

try:
    while True:
        elapsed = time.time() - start_time

        # Determine target temperature by interpolation
        i = bisect_left(times, elapsed)
        if i == 0:
            target_temp = temps[0]
        elif i >= len(times):
            target_temp = temps[-1]
        else:
            t1, t2 = times[i-1], times[i]
            temp1, temp2 = temps[i-1], temps[i]
            frac = (elapsed - t1) / (t2 - t1)
            target_temp = temp1 + frac * (temp2 - temp1)

        pid.setpoint = target_temp
    
        # Try reading temperature with retry on failure
        while True:
            try:
                current_temp = thermocouple.temperature
                if current_temp is None:
                    raise RuntimeError("Invalid temperature reading (None)")

                # Thermocouple recovered
                if thermo_error_active:
                    recovery_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{recovery_time_str}] Thermocouple recovered.")
                    try:
                        recovery_msg = {
                            "text": f"✅ *Kiln Notice*: Thermocouple recovered at {recovery_time_str}."
                        }
                        requests.post(SLACK_WEBHOOK_URL, json=recovery_msg)
                    except requests.RequestException as slack_error:
                        print(f"Slack recovery alert failed: {slack_error}")

                thermo_error_active = False
                last_valid_temp = current_temp  # Save good reading
                break  # exit retry loop

            except RuntimeError as e:
                error_time = time.time()
                error_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 🔥 If we're above 700 °C (1292 °F), ignore and use last valid temp
                if target_temp >= 700:
                    print(f"[{error_time_str}] Ignoring thermocouple error above 700°C: {e}")
                    current_temp = last_valid_temp
                    break

                print(f"[{error_time_str}] Thermocouple error: {e}. Pausing and retrying...")
                GPIO.output(SSR_PIN, GPIO.LOW)  # Turn off heater

                if not thermo_error_active:
                    thermo_error_active = True
                    last_error_alert_time = error_time
                    try:
                        error_msg = {
                            "text": f"⚠️ *Kiln Alert*: Thermocouple error at {error_time_str}.\n"
                                    f"> {str(e)}\nAttempting to reconnect..."
                        }
                        requests.post(SLACK_WEBHOOK_URL, json=error_msg)
                    except requests.RequestException as slack_error:
                        print(f"Slack alert failed: {slack_error}")
                elif error_time - last_error_alert_time >= error_alert_interval:
                    last_error_alert_time = error_time
                    try:
                        update_msg = {
                            "text": f"🔄 *Kiln Status*: Still retrying thermocouple connection...\n"
                                    f"Last error: {str(e)}\nTime: {error_time_str}"
                        }
                        requests.post(SLACK_WEBHOOK_URL, json=update_msg)
                    except requests.RequestException as slack_error:
                        print(f"Slack update alert failed: {slack_error}")

                time.sleep(1)

        # Compute PID output
        output = pid(current_temp)

        # Control SSR
        if output > 0.5:
            GPIO.output(SSR_PIN, GPIO.HIGH)
        else:
            GPIO.output(SSR_PIN, GPIO.LOW)

        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        measured_temp_f = c_to_f(current_temp)
        target_temp_f = c_to_f(target_temp)

        # Slack status update
        if elapsed - last_slack_time > slack_interval:
            send_slack_notification(current_time_str, target_temp_f, measured_temp_f)
            last_slack_time = elapsed

        # Log to file
        log_line = f"{current_time_str},{target_temp_f:.1f},{measured_temp_f:.1f}\n"
        log_file.write(log_line)
        log_file.flush()

        # Console output
        print(f"[{current_time_str}] Target: {target_temp_f:.1f}°F | "
              f"Current: {measured_temp_f:.1f}°F | Output: {output:.2f}")

        time.sleep(1)

except KeyboardInterrupt:
    print("Shutting down kiln controller.")
    log_file.close()
    GPIO.cleanup()
