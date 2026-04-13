import os
import csv
import subprocess
import shutil
from flask import Blueprint, render_template, jsonify, request

homevideos_bp = Blueprint('homevideos', __name__)

# --- Configuration ---
ROOT_DIR = r"C:\Starlight Manor Command"
FFMPEG_EXE = os.path.join(ROOT_DIR, r"utilities\ffmpeg\bin\ffmpeg.exe")
SOURCE_DIR = os.path.join(ROOT_DIR, r"Working\Home Videos\Incoming")
CATALOG_CSV = os.path.join(ROOT_DIR, r"config\home_videos_catalog.csv")
ART_POSTERS = os.path.join(ROOT_DIR, r"Working\Home Videos\Art\Posters")
ART_BACKDROPS = os.path.join(ROOT_DIR, r"Working\Home Videos\Art\Backgrounds")
NAS_DESTINATION = r"\\SM-NAS-01\Media\Home Media"

VALID_EXTENSIONS = ('.mp4', '.m4v', '.mov', '.mkv')

@homevideos_bp.route('/homevideos')
def index():
    return render_template('homevideos.html', active_module='homevideos')

@homevideos_bp.route('/api/catalog', methods=['GET'])
def get_catalog():
    catalog = {}
    try:
        if not os.path.exists(CATALOG_CSV):
            return jsonify({})
        with open(CATALOG_CSV, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                genre = row['genre']
                album = row['album']
                if genre not in catalog:
                    catalog[genre] = []
                if album not in catalog[genre]:
                    catalog[genre].append(album)
        return jsonify(catalog)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@homevideos_bp.route('/api/scan', methods=['GET'])
def scan_files():
    if not os.path.exists(SOURCE_DIR):
        return jsonify([])
    files = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith(VALID_EXTENSIONS)]
    return jsonify(files)

@homevideos_bp.route('/api/publish', methods=['POST'])
def publish_video():
    data = request.json
    filename = data.get('filename')
    title = data.get('title') 
    year = data.get('year')
    desc = data.get('description', '')
    genre = data.get('genre')
    album = data.get('album')

    src_path = os.path.join(SOURCE_DIR, filename)
    
    # Logic Fix: Folder name includes everything for organization
    folder_name = f"{genre} - {album} - {title}"
    dest_dir = os.path.join(NAS_DESTINATION, folder_name)
    
    try:
        # 1. Metadata Injection via FFmpeg
        if os.path.exists(FFMPEG_EXE):
            ext = os.path.splitext(src_path)[1]
            temp_out = src_path.replace(ext, f"_tagged{ext}")
            
            cmd = [
                FFMPEG_EXE, '-y', '-i', src_path,
                '-metadata', f'title={title}',
                '-metadata', f'date={year}',
                '-metadata', f'genre={genre}',
                '-metadata', f'album={album}'
            ]
            
            if desc and desc.strip():
                cmd.extend(['-metadata', f'description={desc}'])
                
            cmd.extend(['-c', 'copy', temp_out])
                
            subprocess.run(cmd, check=True)
            
            # Native Python file swap
            if os.path.exists(src_path):
                os.remove(src_path)
            os.rename(temp_out, src_path)

        # 2. Folder Creation
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        # 3. File Move & Rename
        ext = os.path.splitext(filename)[1]
        final_filename = f"{folder_name}{ext}"
        final_dest = os.path.join(dest_dir, final_filename)
        
        shutil.move(src_path, final_dest)

        # 4. Artwork Copying
        poster_src = os.path.join(ART_POSTERS, f"{album}.jpg")
        bg_src = os.path.join(ART_BACKDROPS, f"{album}.jpg")

        if os.path.exists(poster_src):
            shutil.copy(poster_src, os.path.join(dest_dir, "poster.jpg"))
        if os.path.exists(bg_src):
            shutil.copy(bg_src, os.path.join(dest_dir, "background.jpg"))

        return jsonify({"status": "success", "path": final_dest})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500