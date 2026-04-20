#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Music Ingest Module - Album organization and metadata management
"""

import shutil
import base64
from pathlib import Path
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app

from .music_utils import (
    STAGING, DEST_ROOT, ARTIST_ART_CACHE,
    ensure_dirs, load_genres, manifest_path, write_manifest,
    safe_filename, parse_track_number, parse_disc_number, generate_track_filename,
    read_metadata, write_metadata, iter_audio_files, pick_cover, fetch_artist_art, artist_art_available_quick,
    human_size
)

ingest_bp = Blueprint('music_ingest', __name__)


@ingest_bp.route('/api/ingest/albums')
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


@ingest_bp.route('/api/ingest/scan-sources', methods=['GET'])
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


@ingest_bp.route('/api/ingest/preflight', methods=['POST'])
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


@ingest_bp.route('/api/genres/validate', methods=['POST'])
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


@ingest_bp.route('/api/ingest/update-metadata', methods=['POST'])
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


@ingest_bp.route('/api/ingest/run-batch', methods=['POST'])
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


@ingest_bp.route('/api/ingest/run', methods=['POST'])
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