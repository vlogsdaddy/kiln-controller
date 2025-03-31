from flask import Flask, render_template, request, jsonify
import RPi.GPIO as GPIO

app = Flask(__name__)

# Define GPIO pin for kiln control
KILN_RELAY_PIN = 17  # Change this to the actual pin number
GPIO.setmode(GPIO.BCM)
GPIO.setup(KILN_RELAY_PIN, GPIO.OUT)

# Web Interface
@app.route('/')
def index():
    return '''
    <html>
    <head>
        <title>Kiln Controller</title>
        <script>
            function sendCommand(command) {
                fetch('/control', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: command})
                })
                .then(response => response.json())
                .then(data => alert(data.message));
            }
        </script>
    </head>
    <body>
        <h1>Kiln Controller</h1>
        <button onclick="sendCommand('start')">Start Kiln</button>
        <button onclick="sendCommand('stop')">Stop Kiln</button>
    </body>
    </html>
    '''

# Handle Kiln Control
@app.route('/control', methods=['POST'])
def control():
    data = request.get_json()
    action = data.get('action')
    
    if action == 'start':
        GPIO.output(KILN_RELAY_PIN, GPIO.HIGH)
        return jsonify({'message': 'Kiln started'})
    elif action == 'stop':
        GPIO.output(KILN_RELAY_PIN, GPIO.LOW)
        return jsonify({'message': 'Kiln stopped'})
    else:
        return jsonify({'message': 'Invalid command'}), 400

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        GPIO.cleanup()
