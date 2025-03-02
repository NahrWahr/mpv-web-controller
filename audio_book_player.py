#!/usr/bin/env python3
import json
import socket
import threading
import time
from flask import Flask, request, jsonify, render_template, redirect, url_for

app = Flask(__name__)

# Path to the mpv IPC socket. Adjust if necessary.
MPV_SOCKET_PATH = "/tmp/mpv-socket"

# Store playback state
playback_state = {
    "filename": "Unknown",
    "duration": 0,
    "position": 0,
    "paused": False,
    "speed": 1.0,
    "chapter": 0,
    "chapter_count": 0,
    "volume": 100,
    "last_updated": 0
}

def send_command(command, args=None):
    """
    Sends a JSON command to mpv via its IPC socket and returns the response.
    """
    if args is None:
        args = []
    
    payload = {
        "command": [command] + args,
    }
    
    try:
        # Create a UNIX socket connection
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(MPV_SOCKET_PATH)
        
        # Send the command as a JSON string, ending with a newline
        sock.sendall((json.dumps(payload) + "\n").encode('utf-8'))
        
        # Read the response
        response = sock.recv(1024)
        sock.close()
        
        return json.loads(response.decode('utf-8'))
    except Exception as e:
        print(f"Error communicating with mpv: {e}")
        return {"error": str(e)}

def get_property(property_name):
    """Convenience function to get an mpv property"""
    result = send_command("get_property", [property_name])
    if "data" in result:
        return result["data"]
    return None

def update_playback_state():
    """Updates the playback state with current information from mpv"""
    global playback_state
    
    try:
        playback_state["filename"] = get_property("media-title") or get_property("filename") or "Unknown"
        playback_state["duration"] = get_property("duration") or 0
        playback_state["position"] = get_property("time-pos") or 0
        playback_state["paused"] = get_property("pause") or False
        playback_state["speed"] = get_property("speed") or 1.0
        playback_state["chapter"] = get_property("chapter") or 0
        playback_state["chapter_count"] = get_property("chapter-list/count") or 0
        playback_state["volume"] = get_property("volume") or 100
        playback_state["last_updated"] = time.time()
    except Exception as e:
        print(f"Error updating playback state: {e}")

def state_updater():
    """Background thread to periodically update playback state"""
    while True:
        try:
            update_playback_state()
        except:
            pass
        time.sleep(1)

# Start the background updater thread
update_thread = threading.Thread(target=state_updater, daemon=True)
update_thread.start()

@app.route('/')
def index():
    """Serve the main control page"""
    return render_template('index.html')

@app.route('/api/state')
def get_state():
    """Return the current playback state as JSON"""
    update_playback_state()  # Get fresh state before returning
    return jsonify(playback_state)

@app.route('/api/toggle_pause', methods=['POST'])
def toggle_pause():
    send_command("cycle", ["pause"])
    return jsonify({"status": "success"})

@app.route('/api/stop', methods=['POST'])
def stop():
    send_command("stop")
    return jsonify({"status": "success"})

@app.route('/api/quit', methods=['POST'])
def quit():
    send_command("quit")
    return jsonify({"status": "success", "message": "mpv is quitting..."})

@app.route('/api/seek', methods=['POST'])
def seek():
    data = request.get_json()
    seconds = data.get('seconds', 0)
    send_command("seek", [float(seconds), "relative"])
    return jsonify({"status": "success"})

@app.route('/api/seek_absolute', methods=['POST'])
def seek_absolute():
    data = request.get_json()
    position = data.get('position', 0)
    send_command("seek", [float(position), "absolute"])
    return jsonify({"status": "success"})

@app.route('/api/set_speed', methods=['POST'])
def set_speed():
    data = request.get_json()
    speed = data.get('speed', 1.0)
    send_command("set_property", ["speed", float(speed)])
    return jsonify({"status": "success"})

@app.route('/api/set_volume', methods=['POST'])
def set_volume():
    data = request.get_json()
    volume = data.get('volume', 100)
    send_command("set_property", ["volume", float(volume)])
    return jsonify({"status": "success"})

@app.route('/api/next_chapter', methods=['POST'])
def next_chapter():
    send_command("add", ["chapter", 1])
    return jsonify({"status": "success"})

@app.route('/api/prev_chapter', methods=['POST'])
def prev_chapter():
    send_command("add", ["chapter", -1])
    return jsonify({"status": "success"})

@app.route('/api/skip_forward', methods=['POST'])
def skip_forward():
    send_command("seek", [30, "relative"])
    return jsonify({"status": "success"})

@app.route('/api/skip_backward', methods=['POST'])
def skip_backward():
    send_command("seek", [-10, "relative"])
    return jsonify({"status": "success"})

# Create the templates folder and HTML template
@app.route('/templates/index.html')
def serve_template():
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MPV Remote Control</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        
        body {
            background-color: #121212;
            color: #ffffff;
            padding: 20px;
            max-width: 800px;
            margin: 0 auto;
        }
        
        h1 {
            text-align: center;
            margin-bottom: 20px;
            font-size: 1.8rem;
        }
        
        .card {
            background-color: #1e1e1e;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .now-playing {
            text-align: center;
            margin-bottom: 5px;
        }
        
        .filename {
            font-size: 1.2rem;
            font-weight: bold;
            margin-bottom: 10px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        .playback-info {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 0.9rem;
            color: #aaaaaa;
        }
        
        .progress-container {
            width: 100%;
            height: 30px;
            position: relative;
            margin-bottom: 20px;
        }
        
        .progress-bar {
            width: 100%;
            height: 6px;
            background-color: #333333;
            border-radius: 3px;
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
        }
        
        .progress-fill {
            height: 100%;
            background-color: #1db954;
            border-radius: 3px;
            width: 0%;
        }
        
        .progress-handle {
            width: 16px;
            height: 16px;
            background-color: #ffffff;
            border-radius: 50%;
            position: absolute;
            top: 50%;
            transform: translate(-50%, -50%);
            cursor: pointer;
        }
        
        .control-row {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-bottom: 15px;
        }
        
        .btn {
            background-color: #333333;
            color: white;
            border: none;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background-color 0.2s;
        }
        
        .btn:hover {
            background-color: #444444;
        }
        
        .btn.primary {
            background-color: #1db954;
        }
        
        .btn.primary:hover {
            background-color: #1ed760;
        }
        
        .slider-container {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
        }
        
        .slider-label {
            width: 100px;
            font-size: 0.9rem;
        }
        
        .slider {
            flex: 1;
            -webkit-appearance: none;
            height: 5px;
            border-radius: 5px;
            background: #333333;
            outline: none;
        }
        
        .slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 15px;
            height: 15px;
            border-radius: 50%;
            background: #1db954;
            cursor: pointer;
        }
        
        .slider-value {
            width: 60px;
            text-align: right;
            font-size: 0.9rem;
        }
        
        .skip-controls {
            display: flex;
            justify-content: space-between;
            gap: 10px;
            margin-top: 20px;
        }
        
        .skip-btn {
            flex: 1;
            padding: 12px;
            background-color: #333333;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
            font-size: 0.9rem;
        }
        
        .skip-btn:hover {
            background-color: #444444;
        }
        
        .icon {
            font-size: 24px;
            line-height: 1;
        }
        
        @media (max-width: 480px) {
            body {
                padding: 10px;
            }
            
            h1 {
                font-size: 1.5rem;
            }
            
            .btn {
                width: 45px;
                height: 45px;
            }
            
            .slider-label {
                width: 80px;
            }
        }
    </style>
</head>
<body>
    <h1>MPV Remote Control</h1>
    
    <div class="card">
        <div class="now-playing">Now Playing</div>
        <div id="filename" class="filename">Loading...</div>
        
        <div class="playback-info">
            <div id="current-time">00:00</div>
            <div id="duration">00:00</div>
        </div>
        
        <div class="progress-container" id="progress-container">
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill"></div>
            </div>
            <div class="progress-handle" id="progress-handle"></div>
        </div>
        
        <div class="control-row">
            <button class="btn" id="prev-chapter-btn" title="Previous Chapter">
                <span class="icon">⏮</span>
            </button>
            <button class="btn" id="rewind-btn" title="Rewind 10s">
                <span class="icon">⏪</span>
            </button>
            <button class="btn primary" id="play-pause-btn" title="Play/Pause">
                <span class="icon" id="play-pause-icon">⏸</span>
            </button>
            <button class="btn" id="forward-btn" title="Forward 30s">
                <span class="icon">⏩</span>
            </button>
            <button class="btn" id="next-chapter-btn" title="Next Chapter">
                <span class="icon">⏭</span>
            </button>
        </div>
        
        <div class="slider-container">
            <div class="slider-label">Volume</div>
            <input type="range" min="0" max="100" value="100" class="slider" id="volume-slider">
            <div class="slider-value" id="volume-value">100%</div>
        </div>
        
        <div class="slider-container">
            <div class="slider-label">Speed</div>
            <input type="range" min="50" max="200" value="100" class="slider" id="speed-slider">
            <div class="slider-value" id="speed-value">1.0x</div>
        </div>
        
        <div class="skip-controls">
            <button class="skip-btn" id="skip-back-btn">
                <span class="icon">-10</span> Seconds
            </button>
            <button class="skip-btn" id="skip-forward-btn">
                <span class="icon">+30</span> Seconds
            </button>
        </div>
    </div>
    
    <div class="card">
        <div class="skip-controls">
            <button class="skip-btn" id="stop-btn">Stop</button>
            <button class="skip-btn" id="quit-btn">Quit MPV</button>
        </div>
    </div>

    <script>
        // State variables
        let dragging = false;
        let mpvState = {
            position: 0,
            duration: 0,
            paused: true,
            speed: 1.0,
            volume: 100
        };
        
        // DOM Elements
        const filenameEl = document.getElementById('filename');
        const currentTimeEl = document.getElementById('current-time');
        const durationEl = document.getElementById('duration');
        const progressFillEl = document.getElementById('progress-fill');
        const progressHandleEl = document.getElementById('progress-handle');
        const progressContainerEl = document.getElementById('progress-container');
        const playPauseBtn = document.getElementById('play-pause-btn');
        const playPauseIcon = document.getElementById('play-pause-icon');
        const prevChapterBtn = document.getElementById('prev-chapter-btn');
        const nextChapterBtn = document.getElementById('next-chapter-btn');
        const rewindBtn = document.getElementById('rewind-btn');
        const forwardBtn = document.getElementById('forward-btn');
        const volumeSlider = document.getElementById('volume-slider');
        const volumeValue = document.getElementById('volume-value');
        const speedSlider = document.getElementById('speed-slider');
        const speedValue = document.getElementById('speed-value');
        const skipBackBtn = document.getElementById('skip-back-btn');
        const skipForwardBtn = document.getElementById('skip-forward-btn');
        const stopBtn = document.getElementById('stop-btn');
        const quitBtn = document.getElementById('quit-btn');
        
        // Helper Functions
        function formatTime(seconds) {
            if (!seconds) return '00:00';
            
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        
        function updateProgressBar() {
            const percentage = (mpvState.position / mpvState.duration) * 100 || 0;
            progressFillEl.style.width = `${percentage}%`;
            progressHandleEl.style.left = `${percentage}%`;
            currentTimeEl.textContent = formatTime(mpvState.position);
            durationEl.textContent = formatTime(mpvState.duration);
        }
        
        function updatePlayPauseButton() {
            playPauseIcon.textContent = mpvState.paused ? '▶' : '⏸';
        }
        
        // API Functions
        async function fetchState() {
            try {
                const response = await fetch('/api/state');
                const data = await response.json();
                
                mpvState = {
                    position: data.position || 0,
                    duration: data.duration || 0,
                    paused: data.paused || true,
                    filename: data.filename || 'No file',
                    speed: data.speed || 1.0,
                    volume: data.volume || 100,
                    chapter: data.chapter,
                    chapter_count: data.chapter_count
                };
                
                filenameEl.textContent = mpvState.filename;
                volumeSlider.value = mpvState.volume;
                volumeValue.textContent = `${Math.round(mpvState.volume)}%`;
                speedSlider.value = mpvState.speed * 100;
                speedValue.textContent = `${mpvState.speed.toFixed(1)}x`;
                
                updateProgressBar();
                updatePlayPauseButton();
                
                // Update chapter navigation buttons state
                prevChapterBtn.disabled = mpvState.chapter <= 0;
                nextChapterBtn.disabled = mpvState.chapter >= mpvState.chapter_count - 1;
                
            } catch (error) {
                console.error('Error fetching state:', error);
            }
        }
        
        async function sendCommand(endpoint, data = {}) {
            try {
                const response = await fetch(`/api/${endpoint}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                
                // Immediately update state after command
                setTimeout(fetchState, 100);
                return await response.json();
            } catch (error) {
                console.error(`Error with ${endpoint}:`, error);
            }
        }
        
        // Event Listeners
        playPauseBtn.addEventListener('click', () => {
            sendCommand('toggle_pause');
        });
        
        rewindBtn.addEventListener('click', () => {
            sendCommand('seek', { seconds: -10 });
        });
        
        forwardBtn.addEventListener('click', () => {
            sendCommand('seek', { seconds: 30 });
        });
        
        prevChapterBtn.addEventListener('click', () => {
            sendCommand('prev_chapter');
        });
        
        nextChapterBtn.addEventListener('click', () => {
            sendCommand('next_chapter');
        });
        
        skipBackBtn.addEventListener('click', () => {
            sendCommand('seek', { seconds: -10 });
        });
        
        skipForwardBtn.addEventListener('click', () => {
            sendCommand('seek', { seconds: 30 });
        });
        
        stopBtn.addEventListener('click', () => {
            sendCommand('stop');
        });
        
        quitBtn.addEventListener('click', () => {
            if (confirm('Are you sure you want to quit MPV?')) {
                sendCommand('quit');
            }
        });
        
        volumeSlider.addEventListener('input', () => {
            const value = volumeSlider.value;
            volumeValue.textContent = `${value}%`;
        });
        
        volumeSlider.addEventListener('change', () => {
            const value = volumeSlider.value;
            sendCommand('set_volume', { volume: Number(value) });
        });
        
        speedSlider.addEventListener('input', () => {
            const value = speedSlider.value / 100;
            speedValue.textContent = `${value.toFixed(1)}x`;
        });
        
        speedSlider.addEventListener('change', () => {
            const value = speedSlider.value / 100;
            sendCommand('set_speed', { speed: value });
        });
        
        // Progress bar seeking
        progressContainerEl.addEventListener('mousedown', (e) => {
            dragging = true;
            updateSeekPosition(e);
        });
        
        progressContainerEl.addEventListener('touchstart', (e) => {
            dragging = true;
            updateSeekPosition(e.touches[0]);
        });
        
        document.addEventListener('mousemove', (e) => {
            if (dragging) {
                updateSeekPosition(e);
            }
        });
        
        document.addEventListener('touchmove', (e) => {
            if (dragging) {
                updateSeekPosition(e.touches[0]);
                e.preventDefault();
            }
        });
        
        document.addEventListener('mouseup', () => {
            if (dragging) {
                dragging = false;
                const percentage = parseFloat(progressHandleEl.style.left) / 100;
                const position = percentage * mpvState.duration;
                sendCommand('seek_absolute', { position });
            }
        });
        
        document.addEventListener('touchend', () => {
            if (dragging) {
                dragging = false;
                const percentage = parseFloat(progressHandleEl.style.left) / 100;
                const position = percentage * mpvState.duration;
                sendCommand('seek_absolute', { position });
            }
        });
        
        function updateSeekPosition(e) {
            const rect = progressContainerEl.getBoundingClientRect();
            let x = e.clientX - rect.left;
            x = Math.max(0, Math.min(x, rect.width));
            
            const percentage = (x / rect.width) * 100;
            progressFillEl.style.width = `${percentage}%`;
            progressHandleEl.style.left = `${percentage}%`;
            
            const position = (percentage / 100) * mpvState.duration;
            currentTimeEl.textContent = formatTime(position);
        }
        
        // Initialize and set up polling
        fetchState();
        setInterval(fetchState, 1000);
    </script>
</body>
</html>
    """
    return html

if __name__ == '__main__':
    # Listen on all interfaces so your phone can access it
    app.run(host="0.0.0.0", port=5000, debug=True)
