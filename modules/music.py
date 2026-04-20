#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Music Module - Main entry point with Flask Blueprints
Enhanced version with track renaming support
"""

from flask import Blueprint, render_template, request

from .music_search import search_bp
from .music_ingest import ingest_bp

bp = Blueprint('music', __name__, url_prefix='/music')

# Register sub-blueprints
bp.register_blueprint(search_bp)
bp.register_blueprint(ingest_bp)


@bp.route('/')
def index():
    active_tab = request.args.get('tab', 'search')
    return render_template('music.html', active_module='music', active_tab=active_tab)