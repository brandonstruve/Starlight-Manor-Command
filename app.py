#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Starlight Manor Command - Main Application
A centralized hub for home server management
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, redirect, url_for, send_from_directory
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / "config" / ".env")

# Base directory
BASE_DIR = Path(__file__).parent

# Load configuration
CONFIG_PATH = BASE_DIR / "config" / "settings.json"

def load_config():
    """Load configuration from settings.json"""
    if not CONFIG_PATH.exists():
        # Create default config
        default_config = {
            "server": {
                "host": "127.0.0.1",
                "port": 5270,
                "debug": True
            },
            "hub": {
                "name": "Starlight Manor Command",
                "version": "1.0.0"
            },
            "modules": {
                "photos": {"enabled": True},
                "homevideos": {"enabled": True},
                "phonevideos": {"enabled": True},
                "music": {"enabled": True},
                "people": {"enabled": True},
                "mediastats": {"enabled": False},
                "tools": {"enabled": False},
                "logs": {"enabled": False}
            }
        }
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(default_config, f, indent=2)
        return default_config
    
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

CFG = load_config()

# Initialize Flask app
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "web" / "templates"),
    static_folder=str(BASE_DIR / "web" / "static")
)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "starlight-manor-dev-secret-key")

# Setup logging
log_dir = BASE_DIR / "logs" / "hub"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "hub.log"

handler = RotatingFileHandler(
    str(log_file),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))

app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# Context processor for templates
@app.context_processor
def inject_globals():
    """Inject global variables into all templates"""
    return {
        'hub_name': CFG['hub']['name'],
        'hub_version': CFG['hub']['version'],
        'now': datetime.now,
        'modules': CFG['modules']
    }

# Import and register module blueprints
# Added phonevideos blueprint alongside existing ones
from modules import photos, music, people, homevideos, phonevideos

app.register_blueprint(photos.bp)
app.register_blueprint(music.bp)
app.register_blueprint(people.bp)
app.register_blueprint(homevideos.homevideos_bp)
app.register_blueprint(phonevideos.phonevideos_bp)

# Routes
@app.route('/')
def index():
    """Homepage"""
    app.logger.info("Homepage accessed")
    return render_template('home.html', active_module=None)

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok', 'version': CFG['hub']['version']}

@app.route('/data/<path:filename>')
def serve_data_file(filename):
    """Serve files from data directory (profile photos, etc.)"""
    data_dir = BASE_DIR / 'data'
    return send_from_directory(data_dir, filename)

@app.route('/working/<path:filename>')
def serve_working_file(filename):
    """
    Serve files from the Working directory.
    """
    working_dir = BASE_DIR / 'Working'
    return send_from_directory(working_dir, filename)

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', 
                         error_code=404, 
                         error_message="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    app.logger.error(f"Server error: {e}")
    return render_template('error.html', 
                         error_code=500, 
                         error_message="Internal server error"), 500

if __name__ == '__main__':
    host = CFG['server']['host']
    port = CFG['server']['port']
    debug = CFG['server']['debug']
    
    app.logger.info(f"Starting Starlight Manor Command v{CFG['hub']['version']}")
    app.logger.info(f"Server running on http://{host}:{port}")
    
    print(f"🌟 Starlight Manor Command v{CFG['hub']['version']}")
    print(f"🚀 Server running on http://{host}:{port}")
    print(f"📁 Base directory: {BASE_DIR}")
    print()
    
    app.run(host=host, port=port, debug=debug)