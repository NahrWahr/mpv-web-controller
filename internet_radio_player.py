#!/usr/bin/env python3
import json
import socket
import threading
import time
import os
import subprocess
import logging
from flask import Flask, request, jsonify, Response, render_template, redirect, url_for, send_from_directory

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Radio stations configuration
RADIO_STATIONS = [
    {"name": "Deep Space One", "url": "https://somafm.com/nossl/deepspaceone130.pls", "description": "Ambient space music"},
    {"name": "Lush", "url": "https://somafm.com/nossl/lush130.pls", "description": "Sensuous and mellow vocals"},
    {"name": "Metal", "url": "https://somafm.com/metal130.pls", "description": "Heavy metal radio"},
    {"name": "Drone Zone", "url": "https://somafm.com/dronezone130.pls", "description": "Atmospheric ambient music"},
    {"name": "Sonic Universe", "url": "https://somafm.com/nossl/sonicuniverse130.pls", "description": "Jazz and avant-garde"}
]

class MPVController:
    """Controls the MPV media player through socket communication."""
    
    def __init__(self, socket_path="/tmp/mpvsocket"):
        self.socket_path = socket_path
        self.mpv_process = None
        self.current_station = None
        self.playing = False
        self.volume = 50
        
    def start_mpv(self):
        """Start the MPV media player process with socket control."""
        if self.mpv_process is not None and self.mpv_process.poll() is None:
            logger.info("MPV is already running")
            return
            
        # Remove socket file if it exists
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except OSError as e:
            logger.error(f"Error removing socket file: {e}")
        
        # Start MPV with IPC socket for control
        cmd = ["mpv", "--idle", "--input-ipc-server=" + self.socket_path, "--volume=" + str(self.volume)]
        try:
            self.mpv_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("MPV started with process ID: %s", self.mpv_process.pid)
            # Wait a moment for MPV to create the socket
            time.sleep(1) 
            return True
        except Exception as e:
            logger.error(f"Failed to start MPV: {e}")
            return False
    
    def stop_mpv(self):
        """Stop the MPV media player process."""
        if self.mpv_process is not None:
            try:
                self.mpv_process.terminate()
                self.mpv_process.wait(timeout=5)
                logger.info("MPV process terminated")
            except subprocess.TimeoutExpired:
                self.mpv_process.kill()
                logger.warning("MPV process killed after timeout")
            self.mpv_process = None
            self.playing = False
            self.current_station = None
    
    def send_command(self, command):
        """Send a command to MPV via socket."""
        if not os.path.exists(self.socket_path):
            logger.error("MPV socket does not exist. Is MPV running?")
            return None
        
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(self.socket_path)
                sock.sendall((json.dumps(command) + "\n").encode())
                # Wait for response
                response = sock.recv(1024).decode().strip()
                if response:
                    return json.loads(response)
                return None
        except Exception as e:
            logger.error(f"Error sending command to MPV: {e}")
            return None
    
    def play_station(self, station_idx):
        """Play a radio station by index."""
        if station_idx < 0 or station_idx >= len(RADIO_STATIONS):
            logger.error(f"Invalid station index: {station_idx}")
            return False
        
        if not os.path.exists(self.socket_path):
            success = self.start_mpv()
            if not success:
                return False
        
        station = RADIO_STATIONS[station_idx]
        command = {"command": ["loadfile", station["url"]]}
        
        response = self.send_command(command)
        if response is not None:
            self.current_station = station_idx
            self.playing = True
            logger.info(f"Playing station: {station['name']}")
            return True
        return False
    
    def toggle_pause(self):
        """Toggle play/pause state."""
        if not self.playing:
            if self.current_station is not None:
                return self.play_station(self.current_station)
            return False
        
        command = {"command": ["cycle", "pause"]}
        response = self.send_command(command)
        
        if response is not None:
            self.playing = not self.playing
            state = "paused" if not self.playing else "resumed"
            logger.info(f"Playback {state}")
            return True
        return False
    
    def stop(self):
        """Stop playback."""
        command = {"command": ["stop"]}
        response = self.send_command(command)
        
        if response is not None:
            self.playing = False
            logger.info("Playback stopped")
            return True
        return False
    
    def set_volume(self, volume):
        """Set volume (0-100)."""
        if volume < 0 or volume > 100:
            logger.error(f"Volume must be between 0 and 100, got {volume}")
            return False
        
        command = {"command": ["set_property", "volume", volume]}
        response = self.send_command(command)
        
        if response is not None:
            self.volume = volume
            logger.info(f"Volume set to {volume}")
            return True
        return False
    
    def get_status(self):
        """Get current playback status."""
        # Get current media
        property_commands = [
            {"command": ["get_property", "media-title"]},
            {"command": ["get_property", "volume"]},
            {"command": ["get_property", "pause"]}
        ]
        
        media_title = "Unknown"
        paused = True
        
        try:
            # Get media title
            response = self.send_command(property_commands[0])
            if response and "data" in response:
                media_title = response["data"]
                
            # Get volume
            response = self.send_command(property_commands[1])
            if response and "data" in response:
                self.volume = response["data"]
            
            # Get pause state
            response = self.send_command(property_commands[2])
            if response and "data" in response:
                paused = response["data"]
                self.playing = not paused
                
            return {
                "playing": self.playing,
                "station_index": self.current_station,
                "station_name": RADIO_STATIONS[self.current_station]["name"] if self.current_station is not None else None,
                "media_title": media_title,
                "volume": self.volume
            }
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {
                "playing": self.playing,
                "station_index": self.current_station,
                "station_name": RADIO_STATIONS[self.current_station]["name"] if self.current_station is not None else None,
                "media_title": "Unknown",
                "volume": self.volume
            }

# Initialize the MPV controller
mpv = MPVController()

# Initialize the Flask application
app = Flask(__name__)

# Add enumerate filter to Jinja2
app.jinja_env.filters['enumerate'] = enumerate

# Serve the HTML UI
@app.route('/')
def index():
    """Serve the main page."""
    status = mpv.get_status() if os.path.exists(mpv.socket_path) else {
        "playing": False,
        "station_index": None,
        "station_name": None,
        "media_title": None,
        "volume": mpv.volume
    }
    
    return render_template('index.html', 
                          stations=RADIO_STATIONS, 
                          status=status)

# API endpoint to get the list of available stations
@app.route('/api/stations', methods=['GET'])
def get_stations():
    """Return the list of radio stations."""
    return jsonify(RADIO_STATIONS)

# API endpoint to play a station
@app.route('/api/play/<int:station_idx>', methods=['POST'])
def play_station(station_idx):
    """Play a radio station by index."""
    success = mpv.play_station(station_idx)
    if success:
        return jsonify({"status": "success", "message": f"Playing {RADIO_STATIONS[station_idx]['name']}"})
    else:
        return jsonify({"status": "error", "message": "Failed to play station"}), 500

# API endpoint to pause/resume playback
@app.route('/api/pause', methods=['POST'])
def toggle_pause():
    """Toggle play/pause state."""
    success = mpv.toggle_pause()
    if success:
        state = "paused" if not mpv.playing else "resumed"
        return jsonify({"status": "success", "message": f"Playback {state}"})
    else:
        return jsonify({"status": "error", "message": "Failed to toggle pause"}), 500

# API endpoint to stop playback
@app.route('/api/stop', methods=['POST'])
def stop():
    """Stop playback."""
    success = mpv.stop()
    if success:
        return jsonify({"status": "success", "message": "Playback stopped"})
    else:
        return jsonify({"status": "error", "message": "Failed to stop playback"}), 500

# API endpoint to set volume
@app.route('/api/volume/<int:volume>', methods=['POST'])
def set_volume(volume):
    """Set volume (0-100)."""
    success = mpv.set_volume(volume)
    if success:
        return jsonify({"status": "success", "message": f"Volume set to {volume}"})
    else:
        return jsonify({"status": "error", "message": "Failed to set volume"}), 500

# API endpoint to get current status
@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current playback status."""
    if not os.path.exists(mpv.socket_path):
        return jsonify({
            "playing": False,
            "station_index": None,
            "station_name": None,
            "media_title": None,
            "volume": mpv.volume
        })
    
    status = mpv.get_status()
    return jsonify(status)

# API endpoint to restart MPV if it crashed
@app.route('/api/restart_mpv', methods=['POST'])
def restart_mpv():
    """Restart the MPV process."""
    mpv.stop_mpv()
    success = mpv.start_mpv()
    if success:
        return jsonify({"status": "success", "message": "MPV restarted"})
    else:
        return jsonify({"status": "error", "message": "Failed to restart MPV"}), 500

# API endpoint to shut down MPV
@app.route('/api/shutdown_mpv', methods=['POST'])
def shutdown_mpv():
    """Shut down the MPV process."""
    mpv.stop_mpv()
    return jsonify({"status": "success", "message": "MPV shut down"})

# Serve static files
@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files."""
    return send_from_directory('static', path)

# Create the templates directory and the index.html file inside it
def create_templates():
    """Create the templates directory and index.html file."""
    os.makedirs('templates', exist_ok=True)
    
    with open('templates/index.html', 'w') as f:
        f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Internet Radio Player</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 600px;
            margin: 0 auto;
            padding: 1rem;
            background-color: #f5f5f5;
            color: #333;
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 1.5rem;
        }
        .container {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            padding: 1.5rem;
        }
        .status-panel {
            background-color: #f8f9fa;
            border-radius: 6px;
            padding: 1rem;
            margin-bottom: 1.5rem;
            border-left: 4px solid #3498db;
        }
        .now-playing {
            font-weight: bold;
            margin-bottom: 0.5rem;
        }
        .station-name {
            color: #3498db;
        }
        .media-title {
            font-style: italic;
            color: #7f8c8d;
            font-size: 0.9rem;
        }
        .controls {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
        }
        .controls button {
            flex: 1;
            padding: 0.75rem;
            border: none;
            border-radius: 4px;
            background-color: #3498db;
            color: white;
            cursor: pointer;
            font-weight: bold;
            transition: background-color 0.2s;
        }
        .controls button:hover {
            background-color: #2980b9;
        }
        .controls button:disabled {
            background-color: #bdc3c7;
            cursor: not-allowed;
        }
        .volume-control {
            margin-bottom: 1.5rem;
        }
        .volume-control input {
            width: 100%;
            margin-top: 0.5rem;
        }
        .stations {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        .station-item {
            padding: 0.75rem;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .station-item:last-child {
            border-bottom: none;
        }
        .station-item:hover {
            background-color: #f5f5f5;
        }
        .station-item.active {
            background-color: #e1f5fe;
            border-left: 4px solid #3498db;
        }
        .station-name {
            font-weight: bold;
        }
        .station-description {
            font-size: 0.85rem;
            color: #7f8c8d;
        }
        .utility-buttons {
            display: flex;
            gap: 0.5rem;
            margin-top: 1.5rem;
        }
        .utility-buttons button {
            flex: 1;
            padding: 0.5rem;
            border: none;
            border-radius: 4px;
            background-color: #ecf0f1;
            color: #7f8c8d;
            cursor: pointer;
            font-size: 0.85rem;
            transition: background-color 0.2s;
        }
        .utility-buttons button:hover {
            background-color: #dde4e6;
        }
        .refresh-button {
            display: block;
            width: 100%;
            padding: 0.5rem;
            border: none;
            border-radius: 4px;
            background-color: #2ecc71;
            color: white;
            cursor: pointer;
            margin-top: 1rem;
            font-size: 0.85rem;
        }
        .footer {
            margin-top: 2rem;
            text-align: center;
            font-size: 0.8rem;
            color: #95a5a6;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Internet Radio Player</h1>
        
        <div class="status-panel" id="status-panel">
            <div class="now-playing">Now Playing: <span class="station-name" id="current-station">None</span></div>
            <div class="media-title" id="media-title">Not playing</div>
        </div>

        <div class="controls">
            <button id="play-pause-btn" onclick="togglePlayPause()">Play</button>
            <button id="stop-btn" onclick="stopPlayback()" disabled>Stop</button>
        </div>

        <div class="volume-control">
            <label for="volume-slider">Volume: <span id="volume-value">50</span>%</label>
            <input type="range" id="volume-slider" min="0" max="100" value="50" oninput="updateVolumeUI(this.value)" onchange="setVolume(this.value)">
        </div>

        <h2>Available Stations</h2>
        <ul class="stations" id="stations-list">
            {% for station in stations %}
            <li class="station-item {% if status.station_index == loop.index0 %}active{% endif %}" onclick="playStation({{ loop.index0 }})">
                <div class="station-name">{{ station.name }}</div>
                <div class="station-description">{{ station.description }}</div>
            </li>
            {% endfor %}
        </ul>
        
        <button class="refresh-button" onclick="refreshStatus()">Refresh Status</button>
        
        <div class="utility-buttons">
            <button onclick="restartMPV()">Restart MPV</button>
            <button onclick="shutdownMPV()">Shutdown MPV</button>
        </div>
    </div>
    
    <div class="footer">
        <p>SomaFM Internet Radio Player</p>
    </div>

    <script>
        // Store the current state
        let currentState = {
            playing: {% if status.playing %}true{% else %}false{% endif %},
            stationIndex: {% if status.station_index is not none %}{{ status.station_index }}{% else %}null{% endif %},
            volume: {{ status.volume }}
        };

        // Update UI based on initial state
        updateUI();

        // Play a station
        function playStation(stationIdx) {
            fetch(`/api/play/${stationIdx}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === "success") {
                        currentState.playing = true;
                        currentState.stationIndex = stationIdx;
                        updateUI();
                        setTimeout(refreshStatus, 1000); // Refresh status after a delay
                    } else {
                        alert("Error: " + data.message);
                    }
                })
                .catch(error => {
                    console.error("Error:", error);
                    alert("Failed to play station. Is the server running?");
                });
        }

        // Toggle play/pause
        function togglePlayPause() {
            // If nothing is playing, play the first station
            if (currentState.stationIndex === null) {
                playStation(0);
                return;
            }
            
            fetch('/api/pause', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === "success") {
                        currentState.playing = !currentState.playing;
                        updateUI();
                    } else {
                        alert("Error: " + data.message);
                    }
                })
                .catch(error => {
                    console.error("Error:", error);
                    alert("Failed to toggle playback. Is the server running?");
                });
        }

        // Stop playback
        function stopPlayback() {
            fetch('/api/stop', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === "success") {
                        currentState.playing = false;
                        updateUI();
                    } else {
                        alert("Error: " + data.message);
                    }
                })
                .catch(error => {
                    console.error("Error:", error);
                    alert("Failed to stop playback. Is the server running?");
                });
        }

        // Update volume UI
        function updateVolumeUI(value) {
            document.getElementById('volume-value').textContent = value;
        }

        // Set volume
        function setVolume(value) {
            fetch(`/api/volume/${value}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === "success") {
                        currentState.volume = parseInt(value);
                    } else {
                        alert("Error: " + data.message);
                    }
                })
                .catch(error => {
                    console.error("Error:", error);
                    alert("Failed to set volume. Is the server running?");
                });
        }

        // Restart MPV
        function restartMPV() {
            if (confirm("Are you sure you want to restart MPV?")) {
                fetch('/api/restart_mpv', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === "success") {
                            alert("MPV has been restarted.");
                            currentState.playing = false;
                            currentState.stationIndex = null;
                            updateUI();
                        } else {
                            alert("Error: " + data.message);
                        }
                    })
                    .catch(error => {
                        console.error("Error:", error);
                        alert("Failed to restart MPV. Is the server running?");
                    });
            }
        }

        // Shutdown MPV
        function shutdownMPV() {
            if (confirm("Are you sure you want to shut down MPV?")) {
                fetch('/api/shutdown_mpv', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === "success") {
                            alert("MPV has been shut down.");
                            currentState.playing = false;
                            currentState.stationIndex = null;
                            updateUI();
                        } else {
                            alert("Error: " + data.message);
                        }
                    })
                    .catch(error => {
                        console.error("Error:", error);
                        alert("Failed to shut down MPV. Is the server running?");
                    });
            }
        }

        // Refresh status
        function refreshStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    // Update the current state
                    currentState.playing = data.playing;
                    currentState.stationIndex = data.station_index;
                    currentState.volume = data.volume;
                    
                    // Update the UI
                    document.getElementById('current-station').textContent = 
                        data.station_name ? data.station_name : 'None';
                    document.getElementById('media-title').textContent = 
                        data.media_title ? data.media_title : 'Not playing';
                    
                    updateUI();
                })
                .catch(error => {
                    console.error("Error:", error);
                    // Don't show alert, just log to console
                });
        }

        // Update the UI based on the current state
        function updateUI() {
            // Update play/pause button
            const playPauseBtn = document.getElementById('play-pause-btn');
            playPauseBtn.textContent = currentState.playing ? 'Pause' : 'Play';
            
            // Update stop button
            const stopBtn = document.getElementById('stop-btn');
            stopBtn.disabled = !currentState.playing;
            
            // Update volume slider
            document.getElementById('volume-slider').value = currentState.volume;
            document.getElementById('volume-value').textContent = currentState.volume;
            
            // Update active station
            const stationItems = document.querySelectorAll('.station-item');
            stationItems.forEach((item, index) => {
                if (index === currentState.stationIndex) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });
        }

        // Periodically refresh status
        setInterval(refreshStatus, 5000);
    </script>
</body>
</html>''')

# Create the static directory
def create_static_directory():
    """Create the static directory for CSS, JS, and other static files."""
    os.makedirs('static', exist_ok=True)

# Main entry point
if __name__ == '__main__':
    # Create necessary directories and files
    create_templates()
    create_static_directory()
    
    # Start MPV automatically
    mpv.start_mpv()
    
    # Start the Flask application
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        # Ensure MPV is shut down when the application exits
        mpv.stop_mpv()
