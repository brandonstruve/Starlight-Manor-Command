#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Music Module - Search (NZB) + Ingest (Cover Art & Organization)
Enhanced version with track renaming support
"""

import os
import json
import base64
import shutil
import csv
from pathlib import Path
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, jsonify, current_app
import requests
import xmltodict
from mutagen import File as MutagenFile
from mutagen.id3 import TPE2, TALB, TDRC, TCON, TRCK, TPOS, TIT2

bp = Blueprint('music', __name__, url_prefix='/music')

BASE_DIR = Path(__file__).parent.parent
WORKING_ROOT = BASE_DIR / "Working" / "Music"

STAGING = WORKING_ROOT / "Staging"
DOWNLOADS = WORKING_ROOT / "Downloads"
DEST_ROOT = Path(r"\\SM-NAS-01\Media\Music")
MANIFESTS_DIR = BASE_DIR / "logs" / "music" / "manifests"
ARTIST_ART_CACHE = BASE_DIR / "data" / "artist_art_cache"
# In-memory cache for quick artist-art availability checks (scan-sources)
# Key: normalized artist name -> (available: bool, checked_at: datetime)
_ART_AVAIL_CACHE = {}
_ART_AVAIL_CACHE_TTL = timedelta(hours=24)

GENRE_CSV = BASE_DIR / "config" / "Music_Genres.csv"

AUDIO_EXTS = ('.mp3', '.flac', '.m4a', '.aac', '.ogg', '.wav')
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp')

# Music categories for Newznab (standard audio cats)
MUSIC_CATS = "3000,3010,3020,3030,3040"

# ----- INDEXERS (including DrunkenSlug) ------------------------------------
INDEXERS = []
try:
    if os.environ.get('INDEXER_NZBSU_HOST') and os.environ.get('INDEXER_NZBSU_API_KEY'):
        INDEXERS.append({
            'name': 'nzb.su',
            'host': os.environ['INDEXER_NZBSU_HOST'],
            'apikey': os.environ['INDEXER_NZBSU_API_KEY']
        })
    if os.environ.get('INDEXER_NZBGEEK_HOST') and os.environ.get('INDEXER_NZBGEEK_API_KEY'):
        INDEXERS.append({
            'name': 'NZBGeek',
            'host': os.environ['INDEXER_NZBGEEK_HOST'],
            'apikey': os.environ['INDEXER_NZBGEEK_API_KEY']
        })
    if os.environ.get('INDEXER_NZBPLANET_HOST') and os.environ.get('INDEXER_NZBPLANET_API_KEY'):
        INDEXERS.append({
            'name': 'NZBPlanet',
            'host': os.environ['INDEXER_NZBPLANET_HOST'],
            'apikey': os.environ['INDEXER_NZBPLANET_API_KEY']
        })
    # DrunkenSlug
    if os.environ.get('INDEXER_DRUNKENSLUG_HOST') and os.environ.get('INDEXER_DRUNKENSLUG_API_KEY'):
        INDEXERS.append({
            'name': 'DrunkenSlug',
            'host': os.environ['INDEXER_DRUNKENSLUG_HOST'],
            'apikey': os.environ['INDEXER_DRUNKENSLUG_API_KEY']
        })
except Exception as e:
    print(f"Error loading indexers: {e}")

print("Music module loaded indexers:", INDEXERS)

# ----- NZBGet / AudioDB config ---------------------------------------------
NZBGET_HOST = os.environ.get('NZBGET_HOST', 'http://127.0.0.1:6789')
NZBGET_USER = os.environ.get('NZBGET_USERNAME', 'nzbget')
NZBGET_PASS = os.environ.get('NZBGET_PASSWORD', '')
TADB_API_KEY = os.environ.get('THEAUDIODB_API_KEY', '523532')


def ensure_dirs():
    for path in [STAGING, DOWNLOADS, DEST_ROOT, MANIFESTS_DIR, ARTIST_ART_CACHE]:
        path.mkdir(parents=True, exist_ok=True)


def load_genres():
    genres = []
    if GENRE_CSV.exists():
        with open(GENRE_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                genres.append(row['Genre'])
    return sorted(genres)


def manifest_path(prefix):
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec='seconds').replace(':', '-')
    filename = f"{timestamp}_{prefix}.json"
    return MANIFESTS_DIR / filename


def write_manifest(data, manifest_file):
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def safe_filename(name):
    if not name:
        return "Unknown"
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '-')
    name = name.strip('. ')
    if len(name) > 200:
        name = name[:200]
    return name


def parse_track_number(track_str):
    if not track_str:
        return None
    if '/' in track_str:
        track_str = track_str.split('/')[0]
    try:
        return int(track_str)
    except (ValueError, TypeError):
        return None


def parse_disc_number(disc_str):
    if not disc_str:
        return None
    if '/' in disc_str:
        disc_str = disc_str.split('/')[0]
    try:
        return int(disc_str)
    except (ValueError, TypeError):
        return None


def generate_track_filename(metadata, original_extension):
    album_artist = safe_filename(metadata.get('album_artist', 'Unknown Artist'))
    album = safe_filename(metadata.get('album', 'Unknown Album'))
    title = safe_filename(metadata.get('title', 'Unknown Title'))

    track_num = parse_track_number(metadata.get('track', ''))
    disc_num = parse_disc_number(metadata.get('disc', ''))

    parts = []
    if disc_num and disc_num > 0:
        parts.append(f"{disc_num:02d}")
    if track_num and track_num > 0:
        parts.append(f"{track_num:03d}")
    else:
        parts.append("000")

    parts.extend([album_artist, album, title])
    filename = " - ".join(parts)
    return filename + original_extension


def read_metadata(audio_file):
    try:
        audio = MutagenFile(str(audio_file))
        if audio is None:
            return {}
    except Exception as e:
        current_app.logger.error(f"Error opening file with mutagen: {audio_file} ({e})")
        return {}

    metadata = {}
    try:
        if hasattr(audio, 'tags') and audio.tags:
            tags = audio.tags

            album_artist = None
            if 'TPE2' in tags:
                album_artist = str(tags['TPE2'])
            elif 'albumartist' in tags:
                album_artist = str(tags['albumartist'][0]) if isinstance(tags['albumartist'], list) else str(tags['albumartist'])
            elif 'aART' in tags:
                album_artist = str(tags['aART'][0]) if isinstance(tags['aART'], list) else str(tags['aART'])
            if not album_artist:
                if 'TPE1' in tags:
                    album_artist = str(tags['TPE1'])
                elif 'artist' in tags:
                    album_artist = str(tags['artist'][0]) if isinstance(tags['artist'], list) else str(tags['artist'])
                elif '©ART' in tags:
                    album_artist = str(tags['©ART'][0]) if isinstance(tags['©ART'], list) else str(tags['©ART'])
            metadata['album_artist'] = album_artist or ''

            album = None
            if 'TALB' in tags:
                album = str(tags['TALB'])
            elif 'album' in tags:
                album = str(tags['album'][0]) if isinstance(tags['album'], list) else str(tags['album'])
            elif '©alb' in tags:
                album = str(tags['©alb'][0]) if isinstance(tags['©alb'], list) else str(tags['©alb'])
            metadata['album'] = album or ''

            year = None
            if 'TDRC' in tags:
                year = str(tags['TDRC'])[:4]
            elif 'date' in tags:
                date_val = str(tags['date'][0]) if isinstance(tags['date'], list) else str(tags['date'])
                year = date_val[:4] if date_val else ''
            elif '©day' in tags:
                date_val = str(tags['©day'][0]) if isinstance(tags['©day'], list) else str(tags['©day'])
                year = date_val[:4] if date_val else ''
            metadata['year'] = year or ''

            genre = None
            if 'TCON' in tags:
                genre = str(tags['TCON'])
            elif 'genre' in tags:
                genre = str(tags['genre'][0]) if isinstance(tags['genre'], list) else str(tags['genre'])
            elif '©gen' in tags:
                genre = str(tags['©gen'][0]) if isinstance(tags['©gen'], list) else str(tags['©gen'])
            metadata['genre'] = genre or ''

            track = None
            if 'TRCK' in tags:
                track = str(tags['TRCK'])
            elif 'tracknumber' in tags:
                track = str(tags['tracknumber'][0]) if isinstance(tags['tracknumber'], list) else str(tags['tracknumber'])
            elif 'trkn' in tags:
                track_val = tags['trkn'][0] if isinstance(tags['trkn'], list) else tags['trkn']
                if isinstance(track_val, tuple):
                    track = str(track_val[0])
                else:
                    track = str(track_val)
            metadata['track'] = track or ''

            disc = None
            if 'TPOS' in tags:
                disc = str(tags['TPOS'])
            elif 'discnumber' in tags:
                disc = str(tags['discnumber'][0]) if isinstance(tags['discnumber'], list) else str(tags['discnumber'])
            elif 'disk' in tags:
                disc_val = tags['disk'][0] if isinstance(tags['disk'], list) else tags['disk']
                if isinstance(disc_val, tuple):
                    disc = str(disc_val[0])
                else:
                    disc = str(disc_val)
            metadata['disc'] = disc or ''

            title = None
            if 'TIT2' in tags:
                title = str(tags['TIT2'])
            elif 'title' in tags:
                title = str(tags['title'][0]) if isinstance(tags['title'], list) else str(tags['title'])
            elif '©nam' in tags:
                title = str(tags['©nam'][0]) if isinstance(tags['©nam'], list) else str(tags['©nam'])
            metadata['title'] = title or ''
    except Exception as e:
        current_app.logger.error(f"Error reading tags from {audio_file}: {e}")

    return metadata


def write_metadata(audio_file, album_artist=None, album=None, year=None, genre=None, track=None, disc=None, title=None):
    try:
        audio = MutagenFile(str(audio_file))
        if audio is None:
            return False
        file_ext = audio_file.suffix.lower()
        if file_ext == '.mp3':
            if audio.tags is None:
                audio.add_tags()
            if album_artist is not None:
                audio.tags['TPE2'] = TPE2(encoding=3, text=album_artist)
            if album is not None:
                audio.tags['TALB'] = TALB(encoding=3, text=album)
            if year is not None:
                audio.tags['TDRC'] = TDRC(encoding=3, text=year)
            if genre is not None:
                audio.tags['TCON'] = TCON(encoding=3, text=genre)
            if track is not None:
                audio.tags['TRCK'] = TRCK(encoding=3, text=str(track))
            if disc is not None:
                audio.tags['TPOS'] = TPOS(encoding=3, text=str(disc))
            if title is not None:
                audio.tags['TIT2'] = TIT2(encoding=3, text=title)
        elif file_ext == '.flac':
            if album_artist is not None:
                audio['albumartist'] = album_artist
            if album is not None:
                audio['album'] = album
            if year is not None:
                audio['date'] = year
            if genre is not None:
                audio['genre'] = genre
            if track is not None:
                audio['tracknumber'] = str(track)
            if disc is not None:
                audio['discnumber'] = str(disc)
            if title is not None:
                audio['title'] = title
        elif file_ext in ['.m4a', '.mp4']:
            if audio.tags is None:
                audio.add_tags()
            if album_artist is not None:
                audio.tags['aART'] = album_artist
            if album is not None:
                audio.tags['©alb'] = album
            if year is not None:
                audio.tags['©day'] = year
            if genre is not None:
                audio.tags['©gen'] = genre
            if track is not None:
                try:
                    track_num = int(str(track).split('/')[0]) if '/' in str(track) else int(track)
                    audio.tags['trkn'] = [(track_num, 0)]
                except Exception:
                    pass
            if disc is not None:
                try:
                    disc_num = int(str(disc).split('/')[0]) if '/' in str(disc) else int(disc)
                    audio.tags['disk'] = [(disc_num, 0)]
                except Exception:
                    pass
            if title is not None:
                audio.tags['©nam'] = title
        else:
            if album_artist is not None:
                audio['albumartist'] = album_artist
            if album is not None:
                audio['album'] = album
            if year is not None:
                audio['date'] = year
            if genre is not None:
                audio['genre'] = genre
            if track is not None:
                audio['tracknumber'] = str(track)
            if disc is not None:
                audio['discnumber'] = str(disc)
            if title is not None:
                audio['title'] = title
        audio.save()
        return True
    except Exception as e:
        current_app.logger.error(f"Error writing metadata to {audio_file}: {e}")
        return False


def iter_audio_files(folder):
    for file in folder.iterdir():
        if file.is_file() and file.suffix.lower() in AUDIO_EXTS:
            yield file


def pick_cover(folder):
    images = []
    for file in folder.iterdir():
        if file.is_file() and file.suffix.lower() in IMAGE_EXTS:
            images.append(file)
    if not images:
        return None
    for img in images:
        name_lower = img.stem.lower()
        if 'cover' in name_lower or 'folder' in name_lower or 'album' in name_lower:
            return img
    return images[0]


def fetch_artist_art(artist_name):
    if not artist_name or not TADB_API_KEY:
        return None
    try:
        url = f"https://www.theaudiodb.com/api/v1/json/{TADB_API_KEY}/search.php"
        response = requests.get(url, params={'s': artist_name}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and 'artists' in data and data['artists']:
            artist = data['artists'][0]
            thumb_url = artist.get('strArtistThumb')
            if thumb_url:
                img_response = requests.get(thumb_url, timeout=30)
                img_response.raise_for_status()
                return img_response.content
    except Exception as e:
        current_app.logger.error(f"Error fetching artist art for {artist_name}: {e}")
    return None


def artist_art_available_quick(artist_name):
    """Fast availability check for TheAudioDB artist art (no image download).

    Uses an in-memory TTL cache to keep scan-sources responsive.
    """
    if not artist_name:
        return False

    key = artist_name.strip().lower()
    now = datetime.now()
    cached = _ART_AVAIL_CACHE.get(key)
    if cached:
        available, checked_at = cached
        if now - checked_at <= _ART_AVAIL_CACHE_TTL:
            return available

    try:
        url = f"https://theaudiodb.com/api/v1/json/{TADB_API_KEY}/search.php"
        resp = requests.get(url, params={"s": artist_name}, timeout=3)
        resp.raise_for_status()
        data = resp.json()
        artists = data.get("artists") or []
        if not artists:
            _ART_AVAIL_CACHE[key] = (False, now)
            return False
        thumb = (artists[0] or {}).get("strArtistThumb") or ""
        available = bool(thumb)
        _ART_AVAIL_CACHE[key] = (available, now)
        return available
    except Exception:
        # Treat errors as "not available" for scan purposes (informational only)
        _ART_AVAIL_CACHE[key] = (False, now)
        return False
def human_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def send_to_nzbget(nzb_url, title):
    if not NZBGET_HOST:
        return {'success': False, 'error': 'NZBGet not configured'}
    try:
        response = requests.get(nzb_url, timeout=45)
        response.raise_for_status()
        nzb_content = response.content
        nzb_base64 = base64.b64encode(nzb_content).decode('ascii')
        rpc_url = f"{NZBGET_HOST}/jsonrpc"
        rpc_data = {
            "method": "append",
            "params": [
                safe_filename(title) + ".nzb",
                nzb_base64,
                "Music",
                0,
                False,
                False,
                "",
                0,
                "SCORE",
                []
            ]
        }
        rpc_response = requests.post(
            rpc_url,
            json=rpc_data,
            auth=(NZBGET_USER, NZBGET_PASS) if NZBGET_USER else None,
            timeout=30
        )
        rpc_response.raise_for_status()
        result = rpc_response.json()
        if result.get('result'):
            return {'success': True, 'message': 'Sent to NZBGet', 'nzbget_id': result['result']}
        else:
            return {'success': False, 'error': result.get('error', 'Unknown error')}
    except Exception as e:
        current_app.logger.error(f"Error sending to NZBget: {e}")
        return {'success': False, 'error': str(e)}


@bp.route('/')
def index():
    active_tab = request.args.get('tab', 'search')
    return render_template('music.html', active_module='music', active_tab=active_tab)


@bp.route('/api/search')
def api_search():
    """
    Search NZB indexers and return:
      - merged results
      - per-indexer debug info (name, ok/error, item_count)
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'No search query provided'}), 400

    all_results = []
    indexer_debug = []

    for indexer in INDEXERS:
        try:
            url = f"{indexer['host']}/api"

            # Base params for all indexers
            params = {
                't': 'search',
                'q': query,
                'o': 'json',
                'limit': 100,
                'apikey': indexer['apikey']
            }

            # Only non-DrunkenSlug indexers get the MUSIC_CATS filter.
            if indexer['name'] != 'DrunkenSlug':
                params['cat'] = MUSIC_CATS

            current_app.logger.info(f"[MusicSearch] Querying {indexer['name']} at {url} with params {params}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            # Robust JSON/XML handling, including {"rss": {"channel": ...}} wrappers
            try:
                data = response.json()
            except Exception:
                data = xmltodict.parse(response.text)

            # If there's an 'rss' wrapper, unwrap it
            if isinstance(data, dict) and 'rss' in data and isinstance(data['rss'], dict):
                data = data['rss']

            # ---- KEY FIX: channel detection ----
            if isinstance(data, dict):
                # Some indexers: {"channel": {...}}
                # DrunkenSlug JSON: channel fields + "item" directly at the root
                if 'channel' in data and isinstance(data['channel'], dict):
                    channel = data['channel']
                else:
                    channel = data
            else:
                channel = {}

            items = channel.get('item', [])
            if items and not isinstance(items, list):
                items = [items]

            # Per-indexer debug
            indexer_debug.append({
                'name': indexer['name'],
                'ok': True,
                'item_count': len(items)
            })

            for item in items:
                if not isinstance(item, dict):
                    continue

                title = item.get('title', 'Unknown')
                pub_date = item.get('pubDate', '')
                link = item.get('link', '')
                guid = item.get('guid', '')
                category = item.get('category', 'Unknown') or 'Unknown'

                # For DrunkenSlug, filter to audio-only based on category text.
                if indexer['name'] == 'DrunkenSlug':
                    # DrunkenSlug categories look like "Audio > MP3", "Audio > Lossless", etc.
                    if not category.lower().startswith('audio'):
                        continue

                size = 0
                attrs = item.get('attr') or item.get('newznab:attr')
                if isinstance(attrs, list):
                    for a in attrs:
                        if isinstance(a, dict):
                            # xmltodict for some feeds: {'@attributes': {'name': 'size', 'value': '1234'}}
                            ad = a.get('@attributes') or {}
                            # DrunkenSlug-style: {'_name': 'size', '_value': '1234'}
                            if not ad and ('_name' in a and '_value' in a):
                                ad = {'name': a.get('_name'), 'value': a.get('_value')}
                            if ad.get('name') == 'size':
                                try:
                                    size = int(ad.get('value') or 0)
                                except Exception:
                                    size = 0
                if not size:
                    try:
                        size = int(item.get('size', 0) or 0)
                    except Exception:
                        size = 0

                all_results.append({
                    'title': title,
                    'size': size,
                    'size_str': human_size(size),
                    'pub_date': pub_date,
                    'link': link,
                    'indexer': indexer['name'],
                    'guid': guid,
                    'category': category
                })
        except Exception as e:
            current_app.logger.error(f"Error searching {indexer['name']}: {e}")
            indexer_debug.append({
                'name': indexer['name'],
                'ok': False,
                'error': str(e)
            })

    all_results.sort(key=lambda x: x['pub_date'], reverse=True)

    return jsonify({
        'results': all_results,
        'count': len(all_results),
        'query': query,
        'indexers': indexer_debug
    })


@bp.route('/api/download', methods=['POST'])
def api_download():
    data = request.get_json()
    nzb_url = data.get('nzb_url')
    title = data.get('title', 'Download')
    if not nzb_url:
        return jsonify({'error': 'No NZB URL provided'}), 400
    result = send_to_nzbget(nzb_url, title)
    if result['success']:
        return jsonify(result)
    else:
        try:
            response = requests.get(nzb_url, timeout=45)
            response.raise_for_status()
            filename = safe_filename(title)
            if not filename.lower().endswith('.nzb'):
                filename += '.nzb'
            save_path = DOWNLOADS / filename
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(response.content)
            return jsonify({
                'success': True,
                'message': f'NZBGet failed. Saved to Downloads folder: {filename}',
                'fallback': True,
                'path': str(save_path)
            })
        except Exception as e:
            return jsonify({'error': f'Download failed: {e}'}), 500


@bp.route('/api/ingest/albums')
def api_ingest_albums():
    ensure_dirs()
    albums = []
    for folder in STAGING.iterdir():
        if folder.is_dir():
            audio_count = sum(1 for _ in iter_audio_files(folder))
            has_cover = pick_cover(folder) is not None
            albums.append({
                'name': folder.name,
                'path': str(folder),
                'tracks': audio_count,
                'has_cover': has_cover
            })
    albums.sort(key=lambda x: x['name'].lower())
    return jsonify({'albums': albums, 'count': len(albums)})

@bp.route('/api/ingest/scan-sources', methods=['GET'])
def api_ingest_scan_sources():
    """Bulk scan staging folder and return quick checks per album folder (informational only)."""
    ensure_dirs()
    valid_genres = set(load_genres())

    def genre_status(genre_value):
        g = (genre_value or '').strip()
        if not g:
            return 'missing'
        return 'ok' if g in valid_genres else 'nonstandard'

    def confidence_from_issues(issues):
        if not issues:
            return 'high'
        if len(issues) == 1:
            return 'medium'
        return 'low'

    albums = []
    scanned_at = datetime.now().strftime('%Y-%m-%d %I:%M %p')

    for folder in STAGING.iterdir():
        if not folder.is_dir():
            continue
        if folder.name.startswith('.'):
            continue

        audio_files = list(iter_audio_files(folder))
        track_count = len(audio_files)

        first_file = audio_files[0] if audio_files else None
        md = read_metadata(first_file) if first_file else {}

        album_artist = (md.get('album_artist') or '').strip()
        album = (md.get('album') or '').strip()
        year = (md.get('year') or '').strip()
        genre = (md.get('genre') or '').strip()

        cover = pick_cover(folder)
        has_cover = cover is not None

        cover_base64 = None
        if cover:
            try:
                cover_base64 = base64.b64encode(cover.read_bytes()).decode('utf-8')
            except Exception:
                cover_base64 = None

        # Intended destination preview (same logic as preflight/ingest)
        dest_artist_folder = DEST_ROOT / safe_filename(album_artist) if album_artist else DEST_ROOT / "Unknown Artist"
        if year:
            album_folder_name = f"{safe_filename(album)} ({year})" if album else "Unknown Album"
        else:
            album_folder_name = safe_filename(album) if album else "Unknown Album"
        dest_path = str(dest_artist_folder / album_folder_name)

        # Artist art check (exists OR available via quick lookup)
        artist_img_exists = (dest_artist_folder / "artist.jpg").exists()
        artist_art_available = False
        if album_artist and not artist_img_exists:
            artist_art_available = artist_art_available_quick(album_artist)

        g_status = genre_status(genre)

        issues = []
        if track_count == 0:
            issues.append('No audio tracks detected')
        if not has_cover:
            issues.append('Missing album art')
        if g_status == 'missing':
            issues.append('Missing genre')
        elif g_status == 'nonstandard':
            issues.append('Genre not in standard list')
        if not album_artist:
            issues.append('Missing album artist')
        if not album:
            issues.append('Missing album')
        if not year:
            issues.append('Missing year')
        if not artist_img_exists and not artist_art_available:
            issues.append('Missing artist art')

        confidence = confidence_from_issues(issues)

        albums.append({
            'name': folder.name,
            'path': str(folder),
            'track_count': track_count,
            'album_artist': album_artist,
            'album': album,
            'year': year,
            'genre': genre,
            'dest_path': dest_path,

            # flattened convenience fields (UI can use either nested or flat)
            'has_cover': has_cover,
            'cover_base64': cover_base64,
            'artist_img_exists': artist_img_exists,
            'artist_art_available': artist_art_available,

            'album_art': {
                'has_cover': has_cover,
                'cover_path': str(cover) if cover else None,
                'cover_base64': cover_base64
            },
            'genre_status': g_status,
            'artist_art': {
                'artist_img_exists': artist_img_exists,
                'artist_art_available': artist_art_available
            },
            'confidence': confidence,
            'confidence_reasons': issues
        })

    albums.sort(key=lambda x: x.get('name', '').lower())
    return jsonify({'albums': albums, 'count': len(albums), 'scanned_at': scanned_at})


@bp.route('/api/ingest/preflight', methods=['POST'])
def api_ingest_preflight():
    data = request.get_json()
    album_path = Path(data.get('path', ''))
    if not album_path.exists() or not album_path.is_dir():
        return jsonify({'error': 'Album folder not found'}), 404

    cover = pick_cover(album_path)
    tracks = []
    first_audio_file = None

    for audio_file in sorted(iter_audio_files(album_path)):
        if first_audio_file is None:
            first_audio_file = audio_file
        file_metadata = read_metadata(audio_file)
        new_filename = generate_track_filename(file_metadata, audio_file.suffix.lower())
        tracks.append({
            'filename': audio_file.name,
            'new_filename': new_filename,
            'size': human_size(audio_file.stat().st_size),
            'track': file_metadata.get('track', ''),
            'disc': file_metadata.get('disc', ''),
            'title': file_metadata.get('title', ''),
            'metadata': file_metadata
        })

    tracks.sort(key=lambda t: (
        parse_disc_number(t['disc']) or 0,
        parse_track_number(t['track']) or 999
    ))

    metadata = {}
    if first_audio_file:
        metadata = read_metadata(first_audio_file)

    album_artist = metadata.get('album_artist', '')
    album = metadata.get('album', '')
    year = metadata.get('year', '')
    genre = metadata.get('genre', '')

    dest_artist_folder = DEST_ROOT / safe_filename(album_artist) if album_artist else DEST_ROOT / "Unknown Artist"
    if year:
        album_folder_name = f"{safe_filename(album)} ({year})" if album else "Unknown Album"
    else:
        album_folder_name = safe_filename(album) if album else "Unknown Album"
    dest_album_folder = dest_artist_folder / album_folder_name

    artist_img_exists = (dest_artist_folder / "artist.jpg").exists()
    artist_art_available = False
    if album_artist and not artist_img_exists:
        artist_data = fetch_artist_art(album_artist)
        artist_art_available = artist_data is not None

    genres = load_genres()

    cover_base64 = None
    if cover:
        try:
            with open(cover, 'rb') as f:
                cover_base64 = base64.b64encode(f.read()).decode('utf-8')
        except Exception:
            pass

    return jsonify({
        'album_artist': album_artist,
        'album': album,
        'year': year,
        'genre': genre,
        'tracks': tracks,
        'track_count': len(tracks),
        'has_cover': cover is not None,
        'cover_path': str(cover) if cover else None,
        'cover_base64': cover_base64,
        'dest_path': str(dest_album_folder),
        'artist_img_exists': artist_img_exists,
        'artist_art_available': artist_art_available,
        'genres': genres
    })


@bp.route('/api/genres/validate', methods=['POST'])
def api_validate_genre():
    data = request.get_json()
    genre = data.get('genre', '').strip()

    if not genre:
        return jsonify({'valid': False, 'message': 'No genre provided'})

    valid_genres = load_genres()
    is_valid = genre in valid_genres

    return jsonify({
        'valid': is_valid,
        'genre': genre,
        'message': 'Valid genre' if is_valid else 'Not in standard genre list'
    })


@bp.route('/api/ingest/update-metadata', methods=['POST'])
def api_update_metadata():
    data = request.get_json()
    album_path = Path(data.get('path', ''))
    album_artist = data.get('album_artist', '').strip()
    album = data.get('album', '').strip()
    year = data.get('year', '').strip()
    genre = data.get('genre', '').strip()

    if not album_path.exists() or not album_path.is_dir():
        return jsonify({'error': 'Album folder not found'}), 404

    updated = 0
    failed = 0

    for audio_file in iter_audio_files(album_path):
        existing_metadata = read_metadata(audio_file)
        success = write_metadata(
            audio_file,
            album_artist=album_artist if album_artist else None,
            album=album if album else None,
            year=year if year else None,
            genre=genre if genre else None,
            track=existing_metadata.get('track') or None,
            disc=existing_metadata.get('disc') or None,
            title=existing_metadata.get('title') or None
        )
        if success:
            updated += 1
        else:
            failed += 1

    return jsonify({
        'success': True,
        'updated': updated,
        'failed': failed,
        'message': f'Updated {updated} files' + (f', {failed} failed' if failed > 0 else '')
    })


def _ingest_album_folder(album_path, album_artist='', album='', year=''):
    """Core ingest implementation used by single-album and batch ingest."""
    if not album_artist or not album:
        first_file = next(iter_audio_files(album_path), None)
        if first_file:
            metadata = read_metadata(first_file)
            if not album_artist:
                album_artist = metadata.get('album_artist', 'Unknown Artist')
            if not album:
                album = metadata.get('album', 'Unknown Album')
            if not year:
                year = metadata.get('year', '')

    manifest_file = manifest_path('ingest')
    result = {'success': True, 'actions': []}

    dest_artist_folder = DEST_ROOT / safe_filename(album_artist) if album_artist else DEST_ROOT / "Unknown Artist"
    if year:
        album_folder_name = f"{safe_filename(album)} ({year})" if album else "Unknown Album"
    else:
        album_folder_name = safe_filename(album) if album else "Unknown Album"
    dest_album_folder = dest_artist_folder / album_folder_name
    dest_album_folder.mkdir(parents=True, exist_ok=True)

    audio_files = list(iter_audio_files(album_path))
    for audio_file in audio_files:
        try:
            file_metadata = read_metadata(audio_file)
            new_filename = generate_track_filename(file_metadata, audio_file.suffix.lower())
            dest_file = dest_album_folder / new_filename
            shutil.copy2(str(audio_file), str(dest_file))
            result['actions'].append({
                'action': 'copy_audio',
                'src': str(audio_file),
                'dest': str(dest_file),
                'original_name': audio_file.name,
                'new_name': new_filename,
                'ok': True
            })
        except Exception as e:
            result['actions'].append({
                'action': 'copy_audio',
                'src': str(audio_file),
                'dest': str(dest_file) if 'dest_file' in locals() else 'unknown',
                'ok': False,
                'error': str(e)
            })

    cover = pick_cover(album_path)
    if cover:
        dest_cover = dest_album_folder / f"Cover{cover.suffix.lower()}"
        try:
            shutil.copy2(str(cover), str(dest_cover))
            result['actions'].append({
                'action': 'copy_cover',
                'src': str(cover),
                'dest': str(dest_cover),
                'ok': True
            })
        except Exception as e:
            result['actions'].append({
                'action': 'copy_cover',
                'src': str(cover),
                'dest': str(dest_cover),
                'ok': False,
                'error': str(e)
            })

    dest_artist_img = dest_artist_folder / "artist.jpg"
    if not dest_artist_img.exists():
        artist_data = fetch_artist_art(album_artist)
        if artist_data:
            try:
                slug = album_artist.lower().replace(' ', '-') if album_artist else 'unknown-artist'
                cache_file = ARTIST_ART_CACHE / f"{slug}.jpg"
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(artist_data)
                shutil.copy2(str(cache_file), str(dest_artist_img))
                result['actions'].append({
                    'action': 'fetch_artist',
                    'artist': album_artist,
                    'dest': str(dest_artist_img),
                    'ok': True
                })
            except Exception as e:
                result['actions'].append({
                    'action': 'fetch_artist',
                    'artist': album_artist,
                    'ok': False,
                    'error': str(e)
                })
        else:
            result['actions'].append({
                'action': 'fetch_artist',
                'artist': album_artist,
                'ok': False,
                'error': 'Artist not found on TheAudioDB'
            })

    try:
        shutil.rmtree(album_path)
        result['actions'].append({
            'action': 'cleanup',
            'path': str(album_path),
            'ok': True
        })
    except Exception as e:
        result['actions'].append({
            'action': 'cleanup',
            'path': str(album_path),
            'ok': False,
            'error': str(e)
        })

    manifest_data = {
        'album_artist': album_artist,
        'album': album,
        'year': year,
        'dest_path': str(dest_album_folder),
        'actions': result['actions']
    }
    write_manifest(manifest_data, manifest_file)

    result['manifest'] = str(manifest_file)
    result['dest_path'] = str(dest_album_folder)
    result['album_artist'] = album_artist
    result['album'] = album
    result['year'] = year
    return result


@bp.route('/api/ingest/run-batch', methods=['POST'])
def api_ingest_run_batch():
    """Run ingest for multiple selected staging folders."""
    data = request.get_json() or {}
    items = data.get('items') or data.get('paths') or []
    if not isinstance(items, list) or not items:
        return jsonify({'error': 'No album paths provided'}), 400

    results = []
    ok_count = 0
    fail_count = 0

    for item in items:
        # allow list of strings or list of objects
        if isinstance(item, dict):
            path_str = item.get('path', '')
            album_artist = (item.get('album_artist') or '').strip()
            album = (item.get('album') or '').strip()
            year = (item.get('year') or '').strip()
        else:
            path_str = str(item)
            album_artist = ''
            album = ''
            year = ''

        album_path = Path(path_str)
        if not album_path.exists() or not album_path.is_dir():
            fail_count += 1
            results.append({'path': path_str, 'success': False, 'error': 'Album folder not found'})
            continue

        try:
            res = _ingest_album_folder(album_path, album_artist=album_artist, album=album, year=year)
            ok_count += 1
            results.append({'path': path_str, 'success': True, 'result': res})
        except Exception as e:
            fail_count += 1
            results.append({'path': path_str, 'success': False, 'error': str(e)})

    return jsonify({
        'success': fail_count == 0,
        'ok': ok_count,
        'failed': fail_count,
        'results': results
    })

@bp.route('/api/ingest/run', methods=['POST'])
def api_ingest_run():
    data = request.get_json() or {}
    album_path = Path(data.get('path', ''))
    album_artist = (data.get('album_artist', '') or '').strip()
    album = (data.get('album', '') or '').strip()
    year = (data.get('year', '') or '').strip()

    if not album_path.exists() or not album_path.is_dir():
        return jsonify({'error': 'Album folder not found'}), 404

    try:
        result = _ingest_album_folder(album_path, album_artist=album_artist, album=album, year=year)
        current_app.logger.info(f"Music ingest complete: {result.get('album_artist')} - {result.get('album')}")
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Ingest error: {e}")
        return jsonify({'error': str(e)}), 500
