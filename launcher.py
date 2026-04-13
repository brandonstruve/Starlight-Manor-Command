import subprocess
import socket
import time
import os
import sys

# Configuration
PORT = 5270
HOST = "127.0.0.1"
URL = f"http://{HOST}:{PORT}"
APP_PATH = r"C:\Starlight Manor Command\app.py"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def is_port_open():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, PORT)) == 0

def launch():
    # 1. Start server if not running
    if not is_port_open():
        # Use pythonw to prevent a console window for the Flask app itself
        subprocess.Popen(["pythonw", APP_PATH], creationflags=subprocess.CREATE_NO_WINDOW)
        
        # 2. Wait for port to become active (timeout after 10s)
        start_time = time.time()
        while not is_port_open():
            time.sleep(0.5)
            if time.time() - start_time > 10:
                break

    # 3. Launch Chrome (App Mode makes it feel like a native app)
    subprocess.Popen([CHROME_PATH, f"--app={URL}"])

if __name__ == "__main__":
    launch()