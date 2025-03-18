from flask import Flask, render_template, request, jsonify
import time
import digitalio
import board
import adafruit_max31855
import json
import os
import threading
import requests
import simple_pid

# Initialize the thermocouple sensor
spi = board.SPI()
cs = digitalio.DigitalInOut(board.D5)  # Change this if using a different pin
sensor = adafruit_max31855.MAX31855(spi, cs)

# Initialize the relay
relay = digitalio.DigitalInOut(board.D6)  # Change this if using a different pin
relay.direction = digitalio.Direction.OUTPUT
relay.value = False  # Start with relay off

# Setup Flask app
app = Flask(__name__)

# Store the firing schedule and control variables
firing_schedule = []
relay_status = {'on': False}
kiln_running = {'active': False}

# Presets storage file
PRESETS_FILE = "firing_presets.json"

# Slack webhook URL
SLACK_HOOK_URL = "https://hooks.slack.com/services/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"

# Initialize PID controller
pid = simple_pid.PID(5.0, 0.1, 1.0, setpoint=0)  # Tune these values as needed
pid.output_limits = (0, 1)  # Output range between 0 (off) and 1 (on)

def load_presets():
    if os.path.exists(PRESETS_FILE):
        with open(PRESETS_FILE, 'r') as file:
            return json.load(file)
    return {}

def save_presets(presets):
    with open(PRESETS_FILE, 'w') as file:
        json.dump(presets, file, indent=4)

def send_slack_message(msg):
    try:
        requests.post(SLACK_HOOK_URL, json={'text': msg})
    except Exception as e:
        print(f"Failed to send Slack message: {e}")

def kiln_control_loop():
    while kiln_running['active']:
        if firing_schedule:
            current_time = time.time()
            for step in firing_schedule:
                target_temp = step['target_temp']
                pid.setpoint = target_temp
                
                control = pid(sensor.temperature)
                relay.value = control >= 0.5  # Turn relay on if control output is above threshold
                relay_status['on'] = relay.value
                
                send_slack_message(f"Kiln Update: Current Temp: {sensor.temperature:.1f}°F, Target Temp: {target_temp:.1f}°F")
        time.sleep(10)  # Adjust as needed

@app.route('/')
def index():
    return render_template('index.html')  # Webpage for monitoring and schedule input

@app.route('/temperature')
def get_temperature():
    try:
        temp = sensor.temperature
        return jsonify({'temperature': temp, 'relay_status': relay_status['on']})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    global firing_schedule
    if request.method == 'POST':
        data = request.get_json()
        firing_schedule = data['schedule']
        # Calculate ramp rates
        for i in range(1, len(firing_schedule)):
            start_time_prev = float(firing_schedule[i - 1]['start_time'])
            temp_prev = float(firing_schedule[i - 1]['target_temp'])
            start_time = float(firing_schedule[i]['start_time'])
            temp = float(firing_schedule[i]['target_temp'])
            ramp_rate = (temp - temp_prev) / ((start_time - start_time_prev) / 60)  # °F/hr
            firing_schedule[i]['ramp_rate'] = ramp_rate
        return jsonify({'message': 'Schedule updated successfully'})
    return jsonify({'schedule': firing_schedule})

@app.route('/relay', methods=['POST'])
def control_relay():
    global relay_status
    data = request.get_json()
    if 'state' in data:
        relay.value = data['state']
        relay_status['on'] = relay.value
        return jsonify({'relay_status': relay_status['on']})
    return jsonify({'error': 'Invalid request'}), 400

@app.route('/presets', methods=['GET', 'POST'])
def presets():
    presets = load_presets()
    if request.method == 'POST':
        data = request.get_json()
        name = data.get('name')
        schedule = data.get('schedule')
        if name and schedule:
            presets[name] = schedule
            save_presets(presets)
            return jsonify({'message': f'Preset "{name}" saved successfully'})
        return jsonify({'error': 'Invalid data'}), 400
    return jsonify({'presets': presets})

@app.route('/presets/<name>', methods=['GET'])
def get_preset(name):
    presets = load_presets()
    if name in presets:
        return jsonify({'schedule': presets[name]})
    return jsonify({'error': 'Preset not found'}), 404

@app.route('/kiln/start', methods=['POST'])
def start_kiln():
    if not kiln_running['active']:
        kiln_running['active'] = True
        threading.Thread(target=kiln_control_loop, daemon=True).start()
        send_slack_message("🔥 Kiln firing started!")
        return jsonify({'message': 'Kiln started'})
    return jsonify({'error': 'Kiln is already running'}), 400

@app.route('/kiln/stop', methods=['POST'])
def stop_kiln():
    kiln_running['active'] = False
    relay.value = False
    relay_status['on'] = False
    send_slack_message("❄️ Kiln firing stopped!")
    return jsonify({'message': 'Kiln stopped'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
