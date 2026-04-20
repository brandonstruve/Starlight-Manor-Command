#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Music Utilities Module - Shared helper functions and Mutagen operations
"""

import os
import json
import base64
import csv
from pathlib import Path
from datetime import datetime, timedelta

from flask import current_app
import requests
from mutagen import File as MutagenFile
from mutagen.id3 import TPE2, TALB, TDRC, TCON, TRCK, TPOS, TIT2

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

# NZBGet / AudioDB config
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