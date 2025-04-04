from flask import Flask, render_template, request, jsonify
import RPi.GPIO as GPIO
import json

app = Flask(__name__)

# Define GPIO pin for kiln control
KILN_RELAY_PIN = 17  # Change this to the actual pin number
GPIO.setmode(GPIO.BCM)
GPIO.setup(KILN_RELAY_PIN, GPIO.OUT)

kiln_status = "OFF"
heating_profile = []

# Load and Save Presets
PRESET_FILE = "presets.json"

def load_presets():
    try:
        with open(PRESET_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_presets(presets):
    with open(PRESET_FILE, "w") as file:
        json.dump(presets, file)

presets = load_presets()

@app.route('/get_presets', methods=['GET'])
def get_presets():
    return jsonify(presets)

@app.route('/save_preset', methods=['POST'])
def save_preset():
    data = request.json
    preset_name = data.get("name")
    profile = data.get("profile")
    if preset_name and profile:
        presets[preset_name] = profile
        save_presets(presets)
        return jsonify({"message": "Preset saved successfully!"})
    return jsonify({"message": "Invalid data"}), 400

@app.route('/load_preset', methods=['GET'])
def load_preset():
    preset_name = request.args.get("name")
    if preset_name in presets:
        return jsonify(presets[preset_name])
    return jsonify([])

# Web Interface
@app.route('/')
def index():
    return '''
    <html>
    <head>
        <title>Kiln Controller</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            function sendCommand(command) {
                fetch('/control', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: command})
                })
                .then(response => response.json())
                .then(data => document.getElementById('status').innerText = 'Status: ' + data.status);
            }

            function addRow() {
                let table = document.getElementById("profileTable");
                let row = table.insertRow(-1);
                let timeCell = row.insertCell(0);
                let tempCell = row.insertCell(1);
                let rateCell = row.insertCell(2);

                timeCell.innerHTML = '<input type="number" onchange="updateRates()">';
                tempCell.innerHTML = '<input type="number" onchange="updateRates()">';
                rateCell.innerHTML = '<span>--</span>';
                updateChart();
            }

            function updateRates() {
                let table = document.getElementById("profileTable");
                let rows = table.rows;
                for (let i = 1; i < rows.length; i++) {
                    let prevTime = i > 1 ? rows[i - 1].cells[0].children[0].value : 0;
                    let prevTemp = i > 1 ? rows[i - 1].cells[1].children[0].value : 0;
                    let currTime = rows[i].cells[0].children[0].value;
                    let currTemp = rows[i].cells[1].children[0].value;
                    let rateCell = rows[i].cells[2].children[0];

                    if (prevTime !== "" && prevTemp !== "" && currTime !== "" && currTemp !== "" && currTime != prevTime) {
                        let rate = (currTemp - prevTemp) / (currTime - prevTime);
                        rateCell.innerText = rate.toFixed(2) + ' °F/min';
                    } else {
                        rateCell.innerText = '--';
                    }
                }
                updateChart();
            }

            function updateChart() {
                let times = [];
                let temps = [];
                let table = document.getElementById("profileTable");
                let rows = table.rows;
                for (let i = 1; i < rows.length; i++) {
                    let time = rows[i].cells[0].children[0].value;
                    let temp = rows[i].cells[1].children[0].value;
                    if (time !== "" && temp !== "") {
                        times.push(parseFloat(time));
                        temps.push(parseFloat(temp));
                    }
                }
                chart.data.labels = times;
                chart.data.datasets[0].data = temps;
                chart.update();
            }

            function savePreset() {
                let table = document.getElementById("profileTable");
                let rows = table.rows;
                let profile = [];
                for (let i = 1; i < rows.length; i++) {
                    let time = rows[i].cells[0].children[0].value;
                    let temp = rows[i].cells[1].children[0].value;
                    if (time !== "" && temp !== "") {
                        profile.push({start_time: parseFloat(time), target_temp: parseFloat(temp)});
                    }
                }
                let presetName = prompt("Enter preset name:");
                if (presetName) {
                    fetch('/save_preset', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({name: presetName, profile: profile})
                    })
                    .then(response => response.json())
                    .then(data => alert(data.message));
                }
            }

            function loadPresets() {
                fetch('/get_presets')
                .then(response => response.json())
                .then(data => {
                    let select = document.getElementById("presetSelect");
                    select.innerHTML = "";
                    for (let name in data) {
                        let option = document.createElement("option");
                        option.value = name;
                        option.text = name;
                        select.appendChild(option);
                    }
                });
            }

            function loadPreset() {
                let presetName = document.getElementById("presetSelect").value;
                fetch(`/load_preset?name=${presetName}`)
                .then(response => response.json())
                .then(data => {
                    let table = document.getElementById("profileTable");
                    table.innerHTML = '<tr><th>Start Time (min)</th><th>Target Temp (°F)</th><th>Ramp Rate (°F/min)</th></tr>';
                    data.forEach(entry => {
                        let row = table.insertRow(-1);
                        row.insertCell(0).innerHTML = `<input type="number" value="${entry.start_time}" onchange="updateRates()">`;
                        row.insertCell(1).innerHTML = `<input type="number" value="${entry.target_temp}" onchange="updateRates()">`;
                        row.insertCell(2).innerHTML = '<span>--</span>';
                    });
                    updateRates();
                });
            }

            window.onload = function() {
                let ctx = document.getElementById('tempChart').getContext('2d');
                window.chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'Temperature (°F)',
                            data: [],
                            borderColor: 'red',
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            x: { title: { display: true, text: 'Time (min)' } },
                            y: { title: { display: true, text: 'Temperature (°F)' } }
                        }
                    }
                });
            }
        </script>
    </head>
    <body onload="loadPresets()">
        <h1>Kiln Controller</h1>
        <p id="status">Status: OFF</p>
        <button onclick="sendCommand('start')">Start Kiln</button>
        <button onclick="sendCommand('stop')">Stop Kiln</button>

        <h2>Temperature Profile</h2>
        <canvas id="tempChart" width="400" height="200"></canvas>
        
        <h2>Heating Profile</h2>
        <table border="1" id="profileTable">
            <tr>
                <th>Start Time (min)</th>
                <th>Target Temp (°F)</th>
                <th>Ramp Rate (°F/min)</th>
            </tr>
        </table>
        <button onclick="addRow()">Add Row</button>
        <button onclick="savePreset()">Save Preset</button>
        <select id="presetSelect"></select>
        <button onclick="loadPreset()">Load Preset</button>
    </body>
    </html>
    '''


# Handle Kiln Control
@app.route('/control', methods=['POST'])
def control():
    global kiln_status
    data = request.get_json()
    action = data.get('action')
    
    if action == 'start':
        GPIO.output(KILN_RELAY_PIN, GPIO.HIGH)
        kiln_status = "ON"
    elif action == 'stop':
        GPIO.output(KILN_RELAY_PIN, GPIO.LOW)
        kiln_status = "OFF"
    else:
        return jsonify({'message': 'Invalid command'}), 400
    
    return jsonify({'message': f'Kiln {action}ed', 'status': kiln_status})

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        GPIO.cleanup()
