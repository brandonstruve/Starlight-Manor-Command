#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Music Search Module - NZB search and download functionality
"""

import os
import base64
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app
import requests
import xmltodict

from .music_utils import (
    DOWNLOADS, NZBGET_HOST, NZBGET_USER, NZBGET_PASS, MUSIC_CATS,
    safe_filename, human_size, ensure_dirs
)

search_bp = Blueprint('music_search', __name__)

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


@search_bp.route('/api/search')
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


@search_bp.route('/api/download', methods=['POST'])
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