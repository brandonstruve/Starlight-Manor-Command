#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Starlight Manor Command - Phone Videos Module
Handles scanning, renaming, and ingesting mobile video footage.
"""

import os
import shutil
import random
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, current_app

# Define Blueprint
phonevideos_bp = Blueprint('phonevideos', __name__, url_prefix='/phonevideos')

# Configuration
SOURCE_DIRS = [
    r"C:\Starlight Manor Command\Working\Photos\Raw Import\W. Struve Videos",
    r"C:\Starlight Manor Command\Working\Photos\Raw Import\B. Struve Videos",
    r"C:\Starlight Manor Command\Working\Photos\Raw Import\D. Struve Videos",
    r"C:\Starlight Manor Command\Working\Photos\Raw Import\K. Struve Videos",
    r"C:\Starlight Manor Command\Working\Photos\Raw Import\Other Videos"
]

DEST_BASE = r"\\SM-NAS-01\Media\Footage\Phones"
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.m4v', '.mkv')

@phonevideos_bp.route('/')
def index():
    """Main page for the Phone Videos module"""
    return render_template('phonevideos.html', active_module='phonevideos')

@phonevideos_bp.route('/scan', methods=['GET'])
def scan_files():
    """Scans source folders and returns a preview of the changes"""
    results = []
    
    for source_path in SOURCE_DIRS:
        if not os.path.exists(source_path):
            current_app.logger.warning(f"Source path not found: {source_path}")
            continue
            
        for filename in os.listdir(source_path):
            if filename.lower().endswith(VIDEO_EXTENSIONS):
                full_old_path = os.path.join(source_path, filename)
                
                # Get file creation/modified time for dating
                # On Windows, ctime is often creation; mtime is last modified.
                timestamp = os.path.getmtime(full_old_path)
                dt = datetime.fromtimestamp(timestamp)
                
                # Formatting components
                year = dt.strftime("%Y")
                month_folder = dt.strftime("%Y-%m %B").upper() # e.g. 2026-02 FEBRUARY
                datestring = dt.strftime("%Y%m%d")
                random_suffix = random.randint(1000, 9999)
                
                # Final destination path construction
                new_filename = f"{datestring}__{random_suffix}.mp4"
                full_new_path = os.path.join(DEST_BASE, year, month_folder, new_filename)
                
                results.append({
                    'source_folder': os.path.basename(source_path),
                    'old_name': filename,
                    'old_path': full_old_path,
                    'new_name': new_filename,
                    'new_path': full_new_path
                })
                
    return jsonify(results)

@phonevideos_bp.route('/ingest', methods=['POST'])
def ingest_files():
    """Executes the move operation for the selected files"""
    data = request.json
    files_to_move = data.get('files', [])
    success_count = 0
    errors = []

    for file_info in files_to_move:
        try:
            old_path = file_info['old_path']
            new_path = file_info['new_path']
            
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            
            # Perform the move
            shutil.move(old_path, new_path)
            success_count += 1
        except Exception as e:
            errors.append(f"Error moving {file_info['old_name']}: {str(e)}")
            current_app.logger.error(f"Ingest error: {str(e)}")

    return jsonify({
        'success': True,
        'count': success_count,
        'errors': errors
    })