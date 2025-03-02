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
    command = {"command": ["cycle", "pause"]}
    success = send_mpv_command(command)
    return jsonify({"success": success})

@app.route('/volume/up', methods=['POST'])
def volume_up():
    command = {"command": ["add", "volume", 10]}
    success = send_mpv_command(command)
    return jsonify({"success": success})

@app.route('/volume/down', methods=['POST'])
def volume_down():
    command = {"command": ["add", "volume", -10]}
    success = send_mpv_command(command)
    return jsonify({"success": success})

@app.route('/stop', methods=['POST'])
def stop():
    global mpv_process
    success = False
    if mpv_process is not None:
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
            if mpv_process is not None:
                try:
                    mpv_process.terminate()
                    mpv_process.wait(timeout=5)
                except Exception as e:
                    print("Error terminating mpv:", e)
            cmd = ['mpv', f'--input-ipc-server={MPV_SOCKET}', stream]
            mpv_process = subprocess.Popen(cmd)
            return jsonify({"success": True, "stream": stream})
        else:
            return jsonify({"success": False, "error": "No stream provided"})
    else:
        # Stream launching page with dark deep blue background
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Launch mpv Stream</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
            <style>
                body {
                    padding: 20px;
                    background-color: #061008;
                    color: white;
                }
                .form-label, .form-select, .btn {
                    background-color: #061008;
                    color: white;
                }
                .btn:hover {
                    opacity: 0.8;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="mb-4">Launch mpv Stream</h1>
                <form id="launchForm">
                    <div class="mb-3">
                        <label for="stream" class="form-label">Select a stream:</label>
                        <select name="stream" id="stream" class="form-select">
                            <option value="https://somafm.com/nossl/deepspaceone130.pls">Deep Space One</option>
                            <option value="https://somafm.com/nossl/lush130.pls">Lush</option>
                            <option value="https://somafm.com/metal130.pls">Metal</option>
                            <option value="https://somafm.com/dronezone130.pls">Drone Zone</option>
                            <option value="https://somafm.com/nossl/sonicuniverse130.pls">Sonic Universe</option>
                        </select>
                    </div>
                    <button type="submit" class="btn btn-primary">Launch Stream</button>
                </form>
                <div id="status" class="mt-3"></div>
                <br>
                <a href="/" class="btn btn-secondary">Back to Controller</a>
            </div>
            <script>
                function updateStatus(message, success=true) {
                    const statusDiv = document.getElementById("status");
                    statusDiv.textContent = message;
                    statusDiv.className = success ? "alert alert-success" : "alert alert-danger";
                }
                document.getElementById("launchForm").addEventListener("submit", function(e){
                    e.preventDefault();
                    const formData = new FormData(this);
                    fetch('/launch', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if(data.success) {
                            updateStatus("Stream launched successfully!");
                        } else {
                            updateStatus("Error launching stream: " + data.error, false);
                        }
                    });
                });
            </script>
        </body>
        </html>
        """
        return render_template_string(html)

@app.route('/')
def index():
    # Main controller page with a dark deep blue background and Bootstrap styling
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>mpv Controller</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
            body {
                padding: 20px;
                background-color: #001f3f;
                color: white;
            }
            .btn {
                margin: 5px;
            }
            #status {
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container text-center">
            <h1 class="mb-4">mpv Controller</h1>
            <div class="btn-group" role="group">
                <button class="btn btn-primary" id="toggleBtn">Toggle Play/Pause</button>
                <button class="btn btn-danger" id="stopBtn">Stop</button>
                <button class="btn btn-success" id="volUpBtn">Volume Up</button>
                <button class="btn btn-warning" id="volDownBtn">Volume Down</button>
            </div>
            <br><br>
            <a href="/launch" class="btn btn-secondary">Launch Internet Radio Stream</a>
            <div id="status"></div>
        </div>
        <script>
            function updateStatus(message, success = true) {
                const statusDiv = document.getElementById("status");
                statusDiv.textContent = message;
                statusDiv.className = success ? "alert alert-success" : "alert alert-danger";
            }
            document.getElementById("toggleBtn").addEventListener("click", function(){
                fetch('/toggle', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    updateStatus(data.success ? 'Toggled play/pause successfully' : 'Error toggling play/pause', data.success);
                });
            });
            document.getElementById("stopBtn").addEventListener("click", function(){
                fetch('/stop', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    updateStatus(data.success ? 'mpv stopped successfully' : 'Error stopping mpv', data.success);
                });
            });
            document.getElementById("volUpBtn").addEventListener("click", function(){
                fetch('/volume/up', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    updateStatus(data.success ? 'Volume increased' : 'Error increasing volume', data.success);
                });
            });
            document.getElementById("volDownBtn").addEventListener("click", function(){
                fetch('/volume/down', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    updateStatus(data.success ? 'Volume decreased' : 'Error decreasing volume', data.success);
                });
            });
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
