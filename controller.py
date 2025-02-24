from flask import Flask, render_template_string, jsonify, request
import socket
import json
import subprocess

app = Flask(__name__)

# Path for the mpv IPC socket
MPV_SOCKET = "/tmp/mpvsocket"
# Global variable to hold the current mpv process
mpv_process = None

def send_mpv_command(command):
    """
    Connect to the mpv IPC socket and send a JSON command.
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
    # Send the toggle (cycle pause) command to mpv.
    command = {"command": ["cycle", "pause"]}
    success = send_mpv_command(command)
    return jsonify({"success": success})

@app.route('/launch', methods=['GET', 'POST'])
def launch():
    global mpv_process
    if request.method == 'POST':
        stream = request.form.get('stream')
        if stream:
            # If an mpv process is already running, try to terminate it.
            if mpv_process is not None:
                try:
                    mpv_process.terminate()
                    mpv_process.wait(timeout=5)
                except Exception as e:
                    print("Error terminating mpv:", e)
            # Launch mpv with the selected stream and IPC enabled.
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
    # The main controller page with a Toggle button and link to launch streams.
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>mpv Controller</title>
    </head>
    <body>
        <h1>mpv Controller</h1>
        <button onclick="togglePause()">Toggle Play/Pause</button>
        <br><br>
        <a href="/launch">Launch an Internet Radio Stream</a>
        <script>
            function togglePause(){
                fetch('/toggle', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if(data.success){
                        alert('Toggled play/pause successfully');
                    } else {
                        alert('Error toggling play/pause');
                    }
                });
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == '__main__':
    # Listen on all interfaces so that your phone (on the same WiFi) can access it.
    app.run(host='0.0.0.0', port=5000)
