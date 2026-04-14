#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Photos Module - Ingest, Publish, and Cleanup
- Keeps CITY in filename based on GPS → reverse geocode (fallback UNKNOWN)
- People tags are embedded (no sidecar handling needed)
- Robust EXIF datetime fallback
- UPDATED: Robust GPS detection (EXIF IFD + XMP fallback)
"""

import os
import csv
import json
import re
import shutil
import hashlib
import random
import string
from pathlib import Path
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, current_app
from PIL import Image, ExifTags
from geopy.geocoders import Nominatim

# Create blueprint
bp = Blueprint('photos', __name__, url_prefix='/photos')  # <-- FIXED: add __name__

# Configuration
BASE_DIR = Path(__file__).parent.parent
WORKING_ROOT = BASE_DIR / "Working" / "Photos"

# Paths
RAW_IMPORT = WORKING_ROOT / "Raw Import"
INTAKE = WORKING_ROOT / "Intake"
NEEDS_GPS = WORKING_ROOT / "NeedsGPS"
EXPORT = WORKING_ROOT / "Export"
UPLOAD_ROOM = WORKING_ROOT / "UploadRoom"

LIBRARY_ROOT = Path(r"\\SM-NAS-01\Media\Photos")

MANIFESTS_DIR = BASE_DIR / "logs" / "photos" / "manifests"
GEO_CACHE_PATH = MANIFESTS_DIR / "geo_cache.json"

# Photo extensions
PHOTO_EXTS = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp', '.heic',
              '.dng', '.arw', '.cr2', '.nef', '.rw2', '.orf')

# EXIF tags
EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}
GPS_TAG = EXIF_TAGS.get("GPSInfo", 34853)
DATETIME_ORIG_TAG = EXIF_TAGS.get("DateTimeOriginal", 36867)
DATETIME_TAG = EXIF_TAGS.get("DateTime", 306)
DATETIME_DIGITIZED_TAG = EXIF_TAGS.get("DateTimeDigitized", 36868)

# GPS subtag names
GPSTAGS = ExifTags.GPSTAGS

# Pillow IFD enum (present in recent Pillow)
IFD = getattr(ExifTags, "IFD", None)

# Geocoder (for GPS → City)
geolocator = Nominatim(user_agent="starlight_manor_photos")

# ---------------------------
# Helpers
# ---------------------------

def ensure_dirs():
    """Ensure all required directories exist"""
    for path in [RAW_IMPORT, INTAKE, NEEDS_GPS, EXPORT, UPLOAD_ROOM,
                 LIBRARY_ROOT, MANIFESTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)

def iter_files(root, extensions):
    """Iterate over files with given extensions"""
    if not root.exists():
        return
    for file in root.rglob("*"):
        if file.is_file() and file.suffix.lower() in extensions:
            yield file

def file_hash(path):
    """Calculate SHA-1 hash of file"""
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(1024*1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def is_scanned_source(path):
    """Check if file is from Scanned Photos folder"""
    return "Scanned Photos" in str(path)

# ---------- EXIF/XMP GPS utilities (UPDATED) ----------

def _to_float(num):
    """Convert PIL rational / tuple rational to float safely."""
    try:
        return float(num)
    except Exception:
        pass
    if hasattr(num, "numerator") and hasattr(num, "denominator"):
        try:
            return num.numerator / num.denominator
        except Exception:
            return 0.0
    try:
        n, d = num
        return n / d if d else 0.0
    except Exception:
        return 0.0

def _dms_to_deg(dms):
    """Convert DMS tuple to degrees float."""
    try:
        deg = _to_float(dms[0])
        minutes = _to_float(dms[1])
        seconds = _to_float(dms[2])
        return deg + (minutes / 60.0) + (seconds / 3600.0)
    except Exception:
        return None

def _apply_ref(val, ref):
    if ref is None:
        return val
    if isinstance(ref, bytes):
        ref = ref.decode(errors='ignore')
    if str(ref).upper().startswith(('S','W')):
        return -val
    return val

def _get_exif_gps_dict(exif):
    """
    Return a dict of EXIF GPS tags regardless of whether Pillow exposes
    the GPS block as an IFD pointer (int) or a dict.
    """
    if IFD is not None:
        try:
            gps_ifd = exif.get_ifd(IFD.GPSInfo)  # type: ignore[attr-defined]
            if isinstance(gps_ifd, dict) and gps_ifd:
                return gps_ifd
        except Exception:
            pass
    val = exif.get(GPS_TAG)
    if isinstance(val, dict):
        return val
    return None

def extract_xmp_text(path: Path):
    """Extract the first <x:xmpmeta>...</x:xmpmeta> packet from file bytes."""
    try:
        data = path.read_bytes()
    except Exception:
        return None
    start_tag = b"<x:xmpmeta"
    end_tag = b"</x:xmpmeta>"
    i = data.find(start_tag)
    if i == -1:
        return None
    j = data.find(end_tag, i)
    if j == -1:
        return None
    try:
        return data[i:j+len(end_tag)].decode("utf-8", errors="ignore")
    except Exception:
        return None

def _parse_xmp_decimal_or_dms(val: str):
    """
    Accept decimal ('28.538') or DMS-like ('28, 31, 56.26' or '28°31'56.26"').
    """
    if val is None:
        return None
    s = (val.strip()
           .replace("°", " ")
           .replace("'", " ")
           .replace('"', " ")
           .replace(";", " ")
           .replace(",", " "))
    parts = [p for p in s.split() if p]
    try:
        if len(parts) == 1:
            return float(parts[0])
        deg = float(parts[0]); minutes = float(parts[1]); seconds = float(parts[2]) if len(parts) > 2 else 0.0
        return deg + minutes/60.0 + seconds/3600.0
    except Exception:
        return None

def _read_gps_from_xmp(path: Path):
    """
    Read GPS from XMP: exif:GPSLatitude*, exif:GPSLongitude* (with optional *Ref).
    Returns (lat, lon) or None.
    """
    xmp = extract_xmp_text(path)
    if not xmp:
        return None
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xmp)
    except Exception:
        return None
    ns = {
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'exif': 'http://ns.adobe.com/exif/1.0/'
    }
    raw = {}
    for desc in root.findall('.//rdf:Description', ns):
        for key in ('GPSLatitude','GPSLongitude','GPSLatitudeRef','GPSLongitudeRef'):
            val = desc.get(f'{{{ns["exif"]}}}{key}')
            if val: raw[key] = val
        for key in ('GPSLatitude','GPSLongitude','GPSLatitudeRef','GPSLongitudeRef'):
            elem = desc.find(f'exif:{key}', ns)
            if elem is not None and elem.text:
                raw[key] = elem.text
    if 'GPSLatitude' not in raw or 'GPSLongitude' not in raw:
        return None
    lat = _parse_xmp_decimal_or_dms(raw.get('GPSLatitude'))
    lon = _parse_xmp_decimal_or_dms(raw.get('GPSLongitude'))
    if lat is None or lon is None:
        return None
    lat = _apply_ref(lat, raw.get('GPSLatitudeRef'))
    lon = _apply_ref(lon, raw.get('GPSLongitudeRef'))
    return (lat, lon)

def has_gps(path: Path):
    """
    Quick check if image has GPS metadata.
    UPDATED: robust EXIF IFD read; falls back to XMP GPS.
    """
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return _read_gps_from_xmp(path) is not None
            gps_ifd = _get_exif_gps_dict(exif)
            if gps_ifd:
                gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
                if gps.get('GPSLatitude') and gps.get('GPSLongitude'):
                    return True
            return _read_gps_from_xmp(path) is not None
    except Exception:
        return _read_gps_from_xmp(path) is not None

def _parse_datetime_from_export_filename(path: Path):
    """
    Parse capture datetime from your Lightroom export filename.

    Expected format (as you export):
      YYYY_MM_DD HH_MM_SS  __NNNN.ext

    Example:
      2026_01_13 15_42_50  __0001.jpg

    Returns datetime or None.
    """
    name = path.stem
    # Normalize whitespace to single spaces
    name = re.sub(r"\s+", " ", name).strip()

    m = re.match(r"^(\d{4})_(\d{2})_(\d{2}) (\d{2})_(\d{2})_(\d{2})", name)
    if not m:
        return None
    try:
        yyyy, mm, dd, hh, mi, ss = m.groups()
        return datetime(int(yyyy), int(mm), int(dd), int(hh), int(mi), int(ss))
    except Exception:
        return None

def _parse_exif_datetime(dt_str: str):
    try:
        return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None

def get_exif_datetime(path: Path):
    """
    Get the capture datetime used for renaming/publishing.

    Priority:
      1) EXIF DateTimeOriginal
      2) EXIF DateTime
      3) EXIF DateTimeDigitized
      4) Filename-based datetime (legacy export pattern), only as a last resort

    IMPORTANT:
      - We do NOT fall back to filesystem modified time.
      - If no datetime is found, return None (caller should skip).
    """
    # 1-3) EXIF-based capture datetime
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if exif:
                for tag in (DATETIME_ORIG_TAG, DATETIME_TAG, DATETIME_DIGITIZED_TAG):
                    val = exif.get(tag)
                    if val:
                        dt = _parse_exif_datetime(val)
                        if dt:
                            return dt
    except Exception:
        pass

    # 4) Filename-based capture datetime (legacy pattern; only if present)
    dt = _parse_datetime_from_export_filename(path)
    if dt:
        return dt

    return None
def get_gps_coords(path: Path):
    """
    Extract (lat, lon) as floats, or None if not available/parsable.
    UPDATED: robust EXIF IFD path with XMP fallback.
    """
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if exif:
                gps_ifd = _get_exif_gps_dict(exif)
                if gps_ifd:
                    gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
                    lat_ref = gps.get('GPSLatitudeRef')
                    lat_dms = gps.get('GPSLatitude')
                    lon_ref = gps.get('GPSLongitudeRef')
                    lon_dms = gps.get('GPSLongitude')
                    if lat_ref and lat_dms and lon_ref and lon_dms:
                        lat = _dms_to_deg(lat_dms)
                        lon = _dms_to_deg(lon_dms)
                        if lat is not None and lon is not None:
                            lat = _apply_ref(lat, lat_ref)
                            lon = _apply_ref(lon, lon_ref)
                            return (lat, lon)
    except Exception:
        pass

    return _read_gps_from_xmp(path)

def _load_geo_cache():
    try:
        if GEO_CACHE_PATH.exists():
            with open(GEO_CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_geo_cache(cache: dict):
    try:
        GEO_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(GEO_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def reverse_geocode(lat, lon):
    """
    Convert GPS coordinates to city token for filename.
    Returns uppercase city/town/etc. without spaces; falls back to 'UNKNOWN'.
    Uses a simple on-disk cache to minimize lookups.
    """
    if lat is None or lon is None:
        return 'UNKNOWN'

    key = f"{round(lat, 5)},{round(lon, 5)}"
    cache = _load_geo_cache()
    if key in cache:
        return cache[key]

    try:
        location = geolocator.reverse(f"{lat}, {lon}", exactly_one=True, timeout=10)
        if location and location.address:
            address = (location.raw or {}).get('address', {})
            city = (address.get('city') or
                    address.get('town') or
                    address.get('village') or
                    address.get('hamlet') or
                    address.get('county') or
                    'UNKNOWN')
            token = city.upper().replace(' ', '')
        else:
            token = 'UNKNOWN'
    except Exception as e:
        current_app.logger.error(f"Geocoding error: {e}")
        token = 'UNKNOWN'

    cache[key] = token
    _save_geo_cache(cache)
    return token

def generate_random_string(length=8):
    """Generate random alphanumeric string"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def safe_filename(name):
    """Make filename safe for filesystem"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '-')
    return name.strip('. ')

def manifest_path(prefix):
    """Generate manifest file path"""
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec='seconds').replace(':', '-')
    filename = f"{timestamp}_{prefix}.csv"
    return MANIFESTS_DIR / filename

def write_manifest(rows, manifest_file):
    """Write manifest CSV"""
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    file_exists = manifest_file.exists()
    with open(manifest_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['action', 'src_path', 'dest_path', 'hash', 'reason'])
        for row in rows:
            writer.writerow([
                row.get('action', ''),
                row.get('src_path', ''),
                row.get('dest_path', ''),
                row.get('hash', ''),
                row.get('reason', '')
            ])

# ---------------------------
# Routes
# ---------------------------

@bp.route('/')
def index():
    """Photos module homepage"""
    ensure_dirs()
    current_app.logger.info("Photos module accessed")
    return render_template('photos.html', active_module='photos')

@bp.route('/api/ingest/preflight')
def ingest_preflight():
    """Preview what ingest will do"""
    ensure_dirs()

    details = request.args.get('details', '0') in ('1', 'true', 'yes')
    cap = 100

    # Get existing hashes in working folders
    existing_hashes = set()
    for folder in [INTAKE, NEEDS_GPS]:
        for file in iter_files(folder, PHOTO_EXTS):
            try:
                existing_hashes.add(file_hash(file))
            except Exception:
                pass

    counts = {
        'to_intake': 0,
        'to_needsgps': 0,
        'skip_duplicate': 0,
        'errors': 0
    }

    samples = {
        'to_intake': [],
        'to_needsgps': [],
        'skip_duplicate': [],
        'errors': []
    }

    def add_sample(bucket, item):
        if details and len(samples[bucket]) < cap:
            samples[bucket].append(item)

    # Scan source folders
    if RAW_IMPORT.exists():
        for source_folder in RAW_IMPORT.iterdir():
            if not source_folder.is_dir():
                continue

            for file in iter_files(source_folder, PHOTO_EXTS):
                try:
                    h = file_hash(file)
                except Exception as e:
                    counts['errors'] += 1
                    add_sample('errors', {
                        'path': str(file),
                        'reason': f"hash_error: {e}"
                    })
                    continue

                # Check if duplicate
                if h in existing_hashes:
                    counts['skip_duplicate'] += 1
                    add_sample('skip_duplicate', {
                        'action': 'skip',
                        'src_path': str(file),
                        'dest_path': '',
                        'hash': h,
                        'reason': 'already_in_working'
                    })
                    continue

                # Check GPS for routing only (not required later)
                is_scanned = is_scanned_source(file)
                has_gps_data = False if is_scanned else has_gps(file)

                if has_gps_data:
                    dest = INTAKE / file.name
                    counts['to_intake'] += 1
                    add_sample('to_intake', {
                        'action': 'to_intake',
                        'src_path': str(file),
                        'dest_path': str(dest),
                        'hash': h,
                        'reason': ''
                    })
                else:
                    dest = NEEDS_GPS / file.name
                    counts['to_needsgps'] += 1
                    reason = 'scanner_source' if is_scanned else 'missing_gps'
                    add_sample('to_needsgps', {
                        'action': 'to_needsgps',
                        'src_path': str(file),
                        'dest_path': str(dest),
                        'hash': h,
                        'reason': reason
                    })

    return jsonify({
        'counts': counts,
        'samples': samples if details else {},
        'manifest_hint': str(manifest_path('ingest'))
    })

@bp.route('/api/ingest/run', methods=['POST'])
def ingest_run():
    """Run the ingest process"""
    ensure_dirs()

    manifest_file = manifest_path('ingest')

    # Get existing hashes
    existing_hashes = set()
    for folder in [INTAKE, NEEDS_GPS]:
        for file in iter_files(folder, PHOTO_EXTS):
            try:
                existing_hashes.add(file_hash(file))
            except Exception:
                pass

    performed = []
    failed = []
    success_files = 0

    # Process all source folders
    if RAW_IMPORT.exists():
        for source_folder in RAW_IMPORT.iterdir():
            if not source_folder.is_dir():
                continue

            for file in iter_files(source_folder, PHOTO_EXTS):
                try:
                    h = file_hash(file)
                except Exception as e:
                    failed.append({
                        'action': 'error',
                        'src_path': str(file),
                        'dest_path': '',
                        'hash': '',
                        'reason': f"hash_error: {e}"
                    })
                    continue

                # Skip duplicates
                if h in existing_hashes:
                    failed.append({
                        'action': 'skip',
                        'src_path': str(file),
                        'dest_path': '',
                        'hash': h,
                        'reason': 'already_in_working'
                    })
                    continue

                # Determine destination
                is_scanned = is_scanned_source(file)
                has_gps_data = False if is_scanned else has_gps(file)

                if has_gps_data:
                    dest = INTAKE / file.name
                    action = 'to_intake'
                    reason = ''
                else:
                    dest = NEEDS_GPS / file.name
                    action = 'to_needsgps'
                    reason = 'scanner_source' if is_scanned else 'missing_gps'

                # Move file
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(file), str(dest))
                    performed.append({
                        'action': action,
                        'src_path': str(file),
                        'dest_path': str(dest),
                        'hash': h,
                        'reason': reason
                    })
                    existing_hashes.add(h)
                except Exception as e:
                    failed.append({
                        'action': 'error',
                        'src_path': str(file),
                        'dest_path': str(dest),
                        'hash': h,
                        'reason': f"move_error: {e}"
                    })

    # Write manifest
    write_manifest(performed + failed, manifest_file)

    current_app.logger.info(f"Ingest complete: {len(performed)} performed, {len(failed)} failed")

    if len(failed) > 0:
        return jsonify({"status": "error", "message": f"Ingest failed: {len(failed)} files failed, {len(performed)} succeeded"})
    else:
        return jsonify({"status": "success", "message": f"Ingest complete: {len(performed)} files processed"})

def _build_publish_plan():
    source_files = []
    for folder in (INTAKE, NEEDS_GPS):
        source_files.extend(list(iter_files(folder, PHOTO_EXTS)))

    rows = []
    for file in source_files:
        dt = get_exif_datetime(file)
        coords = get_gps_coords(file)
        hasgps = coords is not None

        status = 'READY'
        reason = ''

        if not dt:
            status = 'SKIP'
            reason = 'missing_datetime'
        elif not hasgps:
            status = 'SKIP'
            reason = 'missing_gps'

        new_date_iso = dt.isoformat(sep=' ', timespec='seconds') if dt else ''

        if dt:
            date_str = dt.strftime('%Y%m%d')
            year = dt.strftime('%Y')
            month = dt.strftime('%Y-%m %B')
        else:
            date_str = ''
            year = ''
            month = ''

        city = reverse_geocode(*coords) if coords else 'UNKNOWN'

        try:
            suffix = file_hash(file)[:8].upper()
        except Exception:
            suffix = generate_random_string()

        new_file_name = f"{date_str}__{city}_{suffix}.JPG" if date_str else ''

        library_dest = str(LIBRARY_ROOT / year / month / new_file_name) if (status != 'SKIP' and new_file_name) else ''
        upload_dest = str(UPLOAD_ROOM / new_file_name) if (status != 'SKIP' and new_file_name) else ''

        rows.append({
            'source_path': str(file),
            'source_file': file.name,
            'new_file_name': new_file_name,
            'library_dest': library_dest,
            'upload_dest': upload_dest,
            'new_date': new_date_iso,
            'has_gps': bool(hasgps),
            'status': status,
            'reason': reason
        })

    # Detect conflicts (duplicate destinations and existing destination files)
    dest_counts = {}
    for r in rows:
        if r['status'] == 'READY' and r['library_dest']:
            dest_counts[r['library_dest']] = dest_counts.get(r['library_dest'], 0) + 1

    for r in rows:
        if r['status'] == 'READY' and r['library_dest']:
            if dest_counts.get(r['library_dest'], 0) > 1:
                r['status'] = 'CONFLICT'
                r['reason'] = 'duplicate_destination'
                continue

            try:
                if Path(r['library_dest']).exists() or Path(r['upload_dest']).exists():
                    r['status'] = 'CONFLICT'
                    r['reason'] = 'destination_exists'
            except Exception:
                pass

    counts = {
        'total': len(rows),
        'ready': sum(1 for r in rows if r['status'] == 'READY'),
        'skipped': sum(1 for r in rows if r['status'] == 'SKIP'),
        'conflicts': sum(1 for r in rows if r['status'] == 'CONFLICT')
    }

    rows.sort(key=lambda r: r['source_path'].lower())

    return counts, rows

@bp.route('/api/publish/preflight')
def publish_preflight():
    """Preview what publish will do (full manifest)."""
    ensure_dirs()

    counts, rows = _build_publish_plan()

    return jsonify({
        'counts': counts,
        'rows': rows,
        'source_dirs': [str(INTAKE), str(NEEDS_GPS)],
        'library_root': str(LIBRARY_ROOT),
        'upload_room': str(UPLOAD_ROOM)
    })

@bp.route('/api/publish/run', methods=['POST'])
def publish_run():
    """Run the publish process."""
    ensure_dirs()

    manifest_file = manifest_path('publish')
    counts, rows = _build_publish_plan()

    performed = []
    failed = []
    success_files = 0

    for r in rows:
        src = r.get('source_path', '')
        status = r.get('status', '')
        reason = r.get('reason', '')

        if status != 'READY':
            failed.append({
                'action': 'skip',
                'src_path': src,
                'dest_path': '',
                'hash': '',
                'reason': reason or f"status_{status.lower()}"
            })
            continue

        upload_dest = r.get('upload_dest', '')
        library_dest = r.get('library_dest', '')

        try:
            src_path = Path(src)
            h = ''
            try:
                h = file_hash(src_path)
            except Exception:
                h = ''

            Path(upload_dest).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_path), str(upload_dest))
            performed.append({
                'action': 'copy_uploadroom',
                'src_path': str(src_path),
                'dest_path': upload_dest,
                'hash': h,
                'reason': ''
            })

            Path(library_dest).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(library_dest))
            performed.append({
                'action': 'move_library',
                'src_path': str(src_path),
                'dest_path': library_dest,
                'hash': h,
                'reason': ''
            })
            success_files += 1

        except Exception as e:
            failed.append({
                'action': 'error',
                'src_path': src,
                'dest_path': '',
                'hash': '',
                'reason': f"publish_error: {e}"
            })

    write_manifest(performed + failed, manifest_file)

    current_app.logger.info(f"Publish complete: {success_files} published, {len(failed)} failed")

    if len(failed) > 0:
        return jsonify({"status": "error", "message": f"Publish failed: {len(failed)} files failed, {success_files} succeeded"})
    else:
        return jsonify({"status": "success", "message": f"Publish complete: {success_files} files published"})



@bp.route('/api/cleanup', methods=['POST'])
def cleanup():
    """Clean all working folders"""
    ensure_dirs()

    folders = [INTAKE, NEEDS_GPS, EXPORT, UPLOAD_ROOM]
    counts = {}

    for folder in folders:
        count = 0
        for file in folder.rglob("*"):
            if file.is_file():
                try:
                    file.unlink()
                    count += 1
                except Exception as e:
                    current_app.logger.error(f"Failed to delete {file}: {e}")

        counts[folder.name] = count

    current_app.logger.info(f"Cleanup complete: {counts}")

    return jsonify({"status": "success", "message": f"Cleanup complete: {sum(counts.values())} files removed"})
