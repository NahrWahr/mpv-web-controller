from flask import Flask, render_template_string, jsonify, request
import socket
import json
import subprocess

app = Flask(__name__)

# Path to the mpv IPC socket
MPV_SOCKET = "/tmp/mpvsocket"
# Global variable to hold the current mpv process
mpv_process = None

def send_mpv_command(command):
    """
    Connect to the mpv IPC socket and send a JSON command.
    Returns True if the command was sent successfully.
    """
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(MPV_SOCKET)
        msg = json.dumps(command).encode('utf-8')
        sock.sendall(msg + b'\n')
        sock.close()
        return True
    except Exception as e:
        print("Error sending command:", e)
        return False

@app.route('/toggle', methods=['POST'])
def toggle():
    # Command to toggle play/pause
    command = {"command": ["cycle", "pause"]}
    success = send_mpv_command(command)
    return jsonify({"success": success})

@app.route('/volume/up', methods=['POST'])
def volume_up():
    # Increase volume by 10%
    command = {"command": ["add", "volume", 10]}
    success = send_mpv_command(command)
    return jsonify({"success": success})

@app.route('/volume/down', methods=['POST'])
def volume_down():
    # Decrease volume by 10%
    command = {"command": ["add", "volume", -10]}
    success = send_mpv_command(command)
    return jsonify({"success": success})

@app.route('/stop', methods=['POST'])
def stop():
    global mpv_process
    success = False
    if mpv_process is not None:
        # Send a quit command via IPC to stop mpv gracefully.
        command = {"command": ["quit"]}
        success = send_mpv_command(command)
        try:
            mpv_process.wait(timeout=5)
        except Exception as e:
            print("Error waiting for mpv to quit:", e)
            mpv_process.terminate()
        mpv_process = None
    return jsonify({"success": success})

@app.route('/launch', methods=['GET', 'POST'])
def launch():
    global mpv_process
    if request.method == 'POST':
        stream = request.form.get('stream')
        if stream:
            # If an mpv process is already running, stop it.
            if mpv_process is not None:
                try:
                    mpv_process.terminate()
                    mpv_process.wait(timeout=5)
                except Exception as e:
                    print("Error terminating mpv:", e)
            # Launch mpv with the selected stream and enable IPC.
            cmd = ['mpv', f'--input-ipc-server={MPV_SOCKET}', stream]
            mpv_process = subprocess.Popen(cmd)
            return jsonify({"success": True, "stream": stream})
        else:
            return jsonify({"success": False, "error": "No stream provided"})
    else:
        # GET: Display a form to select and launch a stream.
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Launch mpv Stream</title>
        </head>
        <body>
            <h1>Launch mpv Stream</h1>
            <form action="/launch" method="POST">
                <label for="stream">Select a stream:</label>
                <select name="stream" id="stream">
                    <option value="https://somafm.com/nossl/deepspaceone130.pls">Deep Space One</option>
                    <option value="https://somafm.com/nossl/lush130.pls">Lush</option>
                    <option value="https://somafm.com/metal130.pls">Metal</option>
                    <option value="https://somafm.com/dronezone130.pls">Drone Zone</option>
                    <option value="https://somafm.com/nossl/sonicuniverse130.pls">Sonic Universe</option>
                </select>
                <input type="submit" value="Launch Stream">
            </form>
            <br>
            <a href="/">Back to Controller</a>
        </body>
        </html>
        """
        return render_template_string(html)

@app.route('/')
def index():
    # Main controller page with buttons for play/pause, stop, volume controls, and stream launch.
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>mpv Controller</title>
    </head>
    <body>
        <h1>mpv Controller</h1>
        <button onclick="togglePause()">Toggle Play/Pause</button>
        <button onclick="stopMpv()">Stop</button>
        <button onclick="volumeUp()">Volume Up</button>
        <button onclick="volumeDown()">Volume Down</button>
        <br><br>
        <a href="/launch">Launch an Internet Radio Stream</a>
        <script>
            function togglePause(){
                fetch('/toggle', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    alert(data.success ? 'Toggled play/pause successfully' : 'Error toggling play/pause');
                });
            }
            function stopMpv(){
                fetch('/stop', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    alert(data.success ? 'mpv stopped' : 'Error stopping mpv');
                });
            }
            function volumeUp(){
                fetch('/volume/up', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    alert(data.success ? 'Volume increased' : 'Error increasing volume');
                });
            }
            function volumeDown(){
                fetch('/volume/down', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    alert(data.success ? 'Volume decreased' : 'Error decreasing volume');
                });
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == '__main__':
    # Listen on all interfaces so your phone (on the same WiFi) can access the server.
    app.run(host='0.0.0.0', port=5000)
