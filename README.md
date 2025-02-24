# mpv Controller via Flask

This project provides a simple Flask-based web interface to control the **mpv** media player on a Linux desktop from any device on the same local network (such as your phone). You can use the interface to:

- Toggle play/pause of the currently playing media.
- Adjust volume (up or down by 10% increments).
- Stop the current stream.
- Launch an Internet radio stream (e.g., from SomaFM) by starting a new mpv instance with the selected stream URL.

## Features

- **Play/Pause Toggle:** Easily switch playback state.
- **Volume Controls:** Increase or decrease volume.
- **Stop Playback:** Gracefully terminate mpv.
- **Launch Internet Radio:** Select from a dropdown list of Internet radio streams.
- **Web Interface:** Control mpv from any device on the same WiFi network.

## Prerequisites

- **Linux Desktop** with [mpv](https://mpv.io/) installed.
- **Python 3** (tested with Python 3.8 and above).
- **Flask** installed in your Python environment.

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/mpv-controller.git
   cd mpv-controller
