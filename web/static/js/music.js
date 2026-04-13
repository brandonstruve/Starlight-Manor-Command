// Music Module JavaScript - Enhanced with filename preview

// State
let searchResults = [];
let currentSort = 'date'; // date, size, name
let currentPage = 1;
const resultsPerPage = 20;
let currentAlbumData = null; // Store current album being previewed

// Tab switching
function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Find which button was clicked
    const clickedBtn = Array.from(document.querySelectorAll('.tab-btn')).find(btn => {
        return btn.textContent.trim().toLowerCase() === tabName;
    });
    if (clickedBtn) {
        clickedBtn.classList.add('active');
    }
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');
    
    // Update URL
    const url = new URL(window.location);
    url.searchParams.set('tab', tabName);
    window.history.pushState({}, '', url);
    
    // Load data if needed
    if (tabName === 'ingest') {
        // Bulk scan view for ingest (Search tab remains untouched)
        scanSources();
    }
}

// Search Music
async function searchMusic() {
    const query = document.getElementById('search-query').value.trim();
    if (!query) {
        showToast('Please enter a search term', 'warning');
        return;
    }
    
    showLoading();
    
    try {
        const data = await fetchAPI(`/music/api/search?q=${encodeURIComponent(query)}`);
        
        searchResults = data.results;
        currentPage = 1;
        
        displayResults();
        
        showToast(`Found ${data.count} results`, 'success');
    } catch (error) {
        showToast('Search failed: ' + error.message, 'error');
        document.getElementById('search-results').innerHTML = '';
    } finally {
        hideLoading();
    }
}

// Display search results
function displayResults() {
    const container = document.getElementById('search-results');
    
    if (searchResults.length === 0) {
        container.innerHTML = '<div class="empty-state">No results found</div>';
        return;
    }
    
    // Sort results
    let sorted = [...searchResults];
    if (currentSort === 'date') {
        sorted.sort((a, b) => (b.pub_date || '').localeCompare(a.pub_date || ''));
    } else if (currentSort === 'size') {
        sorted.sort((a, b) => b.size - a.size);
    } else if (currentSort === 'name') {
        sorted.sort((a, b) => a.title.localeCompare(b.title));
    }
    
    // Pagination
    const totalPages = Math.ceil(sorted.length / resultsPerPage);
    const start = (currentPage - 1) * resultsPerPage;
    const end = start + resultsPerPage;
    const pageResults = sorted.slice(start, end);
    
    // Build HTML
    let html = '<div class="results-header">';
    html += `<div><strong>${sorted.length}</strong> results</div>`;
    html += '<div class="sort-controls">';
    html += '<span style="font-size: 0.75rem; color: var(--text-secondary);">Sort by:</span>';
    html += `<button class="sort-btn ${currentSort === 'date' ? 'active' : ''}" onclick="sortResults('date')">Date</button>`;
    html += `<button class="sort-btn ${currentSort === 'size' ? 'active' : ''}" onclick="sortResults('size')">Size</button>`;
    html += `<button class="sort-btn ${currentSort === 'name' ? 'active' : ''}" onclick="sortResults('name')">Name</button>`;
    html += '</div>';
    html += '</div>';
    
    // Results
    pageResults.forEach(result => {
        html += '<div class="result-item">';
        html += '<div class="result-info">';
        html += `<div class="result-title">${escapeHtml(result.title)}</div>`;
        html += '<div class="result-meta">';
        html += `<span>📦 ${result.size_str}</span>`;
        html += `<span>📅 ${formatDate(result.pub_date)}</span>`;
        html += `<span>🔍 ${result.indexer}</span>`;
        html += `<span>📂 ${result.category}</span>`;
        html += '</div>';
        html += '</div>';
        html += '<div class="result-actions">';
        html += `<button class="btn btn-primary btn-small" onclick="downloadNzb('${result.link}', '${escapeHtml(result.title).replace(/'/g, "\\'")}')">Download</button>`;
        html += '</div>';
        html += '</div>';
    });
    
    // Pagination
    if (totalPages > 1) {
        html += '<div class="pagination">';
        html += `<button class="page-btn" onclick="changePage(1)" ${currentPage === 1 ? 'disabled' : ''}>First</button>`;
        html += `<button class="page-btn" onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>Previous</button>`;
        html += `<span style="margin: 0 16px;">Page ${currentPage} of ${totalPages}</span>`;
        html += `<button class="page-btn" onclick="changePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>Next</button>`;
        html += `<button class="page-btn" onclick="changePage(${totalPages})" ${currentPage === totalPages ? 'disabled' : ''}>Last</button>`;
        html += '</div>';
    }
    
    container.innerHTML = html;
}

// Sort results
function sortResults(sortBy) {
    currentSort = sortBy;
    currentPage = 1;
    displayResults();
}

// Change page
function changePage(page) {
    currentPage = page;
    displayResults();
}

// Download NZB
async function downloadNzb(nzbUrl, title) {
    showLoading();
    
    try {
        const data = await fetchAPI('/music/api/download', {
            method: 'POST',
            body: JSON.stringify({
                nzb_url: nzbUrl,
                title: title
            })
        });
        
        if (data.fallback) {
            showToast(data.message, 'warning');
        } else {
            showToast(data.message, 'success');
        }
    } catch (error) {
        showToast('Download failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Load albums from staging
async function loadAlbums() {
    showLoading();
    
    try {
        const data = await fetchAPI('/music/api/ingest/albums');
        
        const container = document.getElementById('albums-list');
        
        if (data.albums.length === 0) {
            container.innerHTML = '<div class="empty-state">No albums in staging folder.<br><br>Place albums in: C:\\Starlight Manor Command\\Working\\Music\\Staging\\</div>';
            return;
        }
        
        let html = '';
        data.albums.forEach(album => {
            html += '<div class="album-item">';
            html += '<div class="album-info">';
            html += `<div class="album-name">${escapeHtml(album.name)}</div>`;
            html += '<div class="album-meta">';
            html += `<span>🎵 ${album.tracks} track${album.tracks !== 1 ? 's' : ''}</span>`;
            if (album.has_cover) {
                html += '<span>🖼️ Has cover</span>';
            }
            html += '</div>';
            html += '</div>';
            html += '<div class="album-actions">';
            html += `<button class="btn btn-secondary btn-small" onclick='previewAlbum(${JSON.stringify(album)})'>Preview</button>`;
            html += `<button class="btn btn-primary btn-small" onclick='runIngestQuick(${JSON.stringify(album)})'>Quick Ingest</button>`;
            html += '</div>';
            html += '</div>';
        });
        
        container.innerHTML = html;
    } catch (error) {
        showToast('Failed to load albums: ' + error.message, 'error');
        document.getElementById('albums-list').innerHTML = '';
    } finally {
        hideLoading();
    }
}

// Preview album before ingest
async function previewAlbum(album) {
    showLoading();
    
    try {
        const data = await fetchAPI('/music/api/ingest/preflight', {
            method: 'POST',
            body: JSON.stringify({
                path: album.path
            })
        });
        
        // Store the album data
        currentAlbumData = {
            path: album.path,
            ...data
        };
        
        // Populate form fields
        document.getElementById('edit-artist').value = data.album_artist || '';
        document.getElementById('edit-album').value = data.album || '';
        document.getElementById('edit-year').value = data.year || '';
        
        // Set up genre field with validation
        const genreInput = document.getElementById('edit-genre');
        genreInput.value = data.genre || '';
        
        // Populate genre dropdown
        const genreSelect = document.getElementById('genre-select');
        genreSelect.innerHTML = '<option value="">-- Select from standard genres --</option>';
        data.genres.forEach(genre => {
            const option = document.createElement('option');
            option.value = genre;
            option.textContent = genre;
            genreSelect.appendChild(option);
        });
        
        // Add event listener to update input when dropdown changes
        genreSelect.onchange = function() {
            if (this.value) {
                genreInput.value = this.value;
                validateGenre(this.value, data.genres);
            }
        };
        
        // Add event listener to validate genre on input change
        genreInput.oninput = function() {
            validateGenre(this.value, data.genres);
        };
        
        // Initial genre validation
        validateGenre(data.genre, data.genres);
        
        // Show cover image
        if (data.cover_base64) {
            document.getElementById('preview-cover-img').src = 'data:image/jpeg;base64,' + data.cover_base64;
        } else {
            document.getElementById('preview-cover-img').src = '/static/img/no-cover.png';
        }
        
        // Show info
        document.getElementById('preview-track-count').textContent = data.track_count;
        document.getElementById('preview-dest-path').textContent = data.dest_path;
        
        // Show artist status
        const artistStatus = document.getElementById('preview-artist-status');
        if (data.artist_img_exists) {
            artistStatus.innerHTML = '<span style="color: var(--success)">✅ Artist image already exists</span>';
        } else if (data.artist_art_available) {
            artistStatus.innerHTML = '<span style="color: var(--info)">🔍 Artist image will be downloaded from TheAudioDB</span>';
        } else if (!data.album_artist) {
            artistStatus.innerHTML = '';
        } else {
            artistStatus.innerHTML = '<span style="color: var(--warning)">⚠️ Artist image not found on TheAudioDB</span>';
        }
        
        // Show track list with renaming preview
        const trackList = document.getElementById('preview-track-list');
        if (data.tracks.length > 0) {
            let tracksHtml = '<div style="margin-bottom: 8px; padding: 8px; background: rgba(255,215,0,0.1); border-radius: 4px; font-size: 0.75rem; color: var(--accent-gold);">';
            tracksHtml += '📝 Files will be renamed during ingest based on metadata';
            tracksHtml += '</div>';
            
            data.tracks.forEach(track => {
                tracksHtml += '<div class="track-item" style="flex-direction: column; align-items: stretch; gap: 4px; padding: 12px;">';
                
                // Original filename
                tracksHtml += '<div style="display: flex; justify-content: space-between; align-items: center;">';
                tracksHtml += '<div>';
                tracksHtml += '<span style="font-size: 0.75rem; color: var(--text-secondary);">Current: </span>';
                tracksHtml += `<span class="track-name" style="color: var(--text-secondary);">${escapeHtml(track.filename)}</span>`;
                tracksHtml += '</div>';
                tracksHtml += `<span class="track-size">${track.size}</span>`;
                tracksHtml += '</div>';
                
                // New filename
                tracksHtml += '<div>';
                tracksHtml += '<span style="font-size: 0.75rem; color: var(--accent-gold);">New: </span>';
                tracksHtml += `<span class="track-name" style="color: var(--accent-gold); font-weight: 500;">${escapeHtml(track.new_filename)}</span>`;
                tracksHtml += '</div>';
                
                tracksHtml += '</div>';
            });
            trackList.innerHTML = tracksHtml;
        } else {
            trackList.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 16px;">No tracks found</p>';
        }
        
        // Show modal
        document.getElementById('preview-modal').style.display = 'flex';
        
    } catch (error) {
        showToast('Preview failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Validate genre against the standard list
function validateGenre(genre, validGenres) {
    const validationSpan = document.getElementById('genre-validation');
    if (!genre) {
        validationSpan.innerHTML = '';
        return;
    }
    
    if (validGenres.includes(genre)) {
        validationSpan.innerHTML = '<span class="genre-valid">✅</span>';
    } else {
        validationSpan.innerHTML = '<span class="genre-invalid" title="Not in standard genre list">⚠️</span>';
    }
}

// Close preview modal
function closePreviewModal() {
    document.getElementById('preview-modal').style.display = 'none';
    currentAlbumData = null;
}

// Update metadata and then run ingest
async function updateMetadataAndIngest() {
    if (!currentAlbumData) {
        showToast('No album data', 'error');
        return;
    }
    
    // Get values from form
    const artist = document.getElementById('edit-artist').value.trim();
    const album = document.getElementById('edit-album').value.trim();
    const year = document.getElementById('edit-year').value.trim();
    const genre = document.getElementById('edit-genre').value.trim();
    
    if (!artist || !album) {
        showToast('Album Artist and Album are required', 'warning');
        return;
    }
    
    showLoading();
    
    try {
        // First, update the metadata in all files
        const updateData = await fetchAPI('/music/api/ingest/update-metadata', {
            method: 'POST',
            body: JSON.stringify({
                path: currentAlbumData.path,
                album_artist: artist,
                album: album,
                year: year,
                genre: genre
            })
        });
        
        console.log('Metadata updated:', updateData.message);
        
        // Then run the ingest
        const ingestData = await fetchAPI('/music/api/ingest/run', {
            method: 'POST',
            body: JSON.stringify({
                path: currentAlbumData.path,
                album_artist: artist,
                album: album,
                year: year,
                genre: genre
            })
        });
        
        // Close modal first
        closePreviewModal();
        
        // Show results
        const successCount = ingestData.actions.filter(a => a.ok).length;
        const failCount = ingestData.actions.filter(a => !a.ok).length;
        
        let message = `Ingest complete!\n\n`;
        message += `📝 Metadata updated in ${updateData.updated} files\n`;
        message += `✅ ${successCount} actions successful\n`;
        if (failCount > 0) {
            message += `❌ ${failCount} actions failed\n`;
        }
        
        // Show renamed files
        const renamedFiles = ingestData.actions.filter(a => a.action === 'copy_audio' && a.ok);
        if (renamedFiles.length > 0 && renamedFiles.some(f => f.original_name !== f.new_name)) {
            message += `\n📁 Files renamed:\n`;
            let renamedCount = 0;
            renamedFiles.forEach(file => {
                if (file.original_name !== file.new_name) {
                    if (renamedCount < 5) {
                        message += `  • ${file.new_name}\n`;
                    }
                    renamedCount++;
                }
            });
            if (renamedCount > 5) {
                message += `  ... and ${renamedCount - 5} more\n`;
            }
        }
        
        message += `\nDestination: ${currentAlbumData.dest_path}`;
        
        alert(message);
        
        // Refresh album list
        loadAlbums();
        
    } catch (error) {
        showToast('Process failed: ' + error.message, 'error');
        hideLoading();
    }
}

// Legacy function for compatibility - redirects to new function
async function runIngestFromModal() {
    await updateMetadataAndIngest();
}

// Run ingest quickly (without preview)
async function runIngestQuick(album) {
    if (!confirm('This will process the album with default settings. Use Preview to customize. Continue?')) {
        return;
    }
    
    await runIngest(album.path);
}

// Run ingest
async function runIngest(albumPath, artist = '', album = '', year = '', genre = '') {
    showLoading();
    
    try {
        const data = await fetchAPI('/music/api/ingest/run', {
            method: 'POST',
            body: JSON.stringify({
                path: albumPath,
                album_artist: artist,
                album: album,
                year: year,
                genre: genre
            })
        });
        
        const successCount = data.actions.filter(a => a.ok).length;
        const failCount = data.actions.filter(a => !a.ok).length;
        
        let message = `Ingest complete!\n\n`;
        message += `✅ ${successCount} actions successful\n`;
        if (failCount > 0) {
            message += `❌ ${failCount} actions failed\n`;
        }
        
        // Show renamed files
        const renamedFiles = data.actions.filter(a => a.action === 'copy_audio' && a.ok);
        if (renamedFiles.length > 0) {
            message += `\n📝 Files renamed:\n`;
            renamedFiles.forEach(file => {
                if (file.original_name !== file.new_name) {
                    message += `  • ${file.original_name} → ${file.new_name}\n`;
                }
            });
        }
        
        message += `\nManifest: ${data.manifest}`;
        
        alert(message);
        
        // Refresh album list
        loadAlbums();
    } catch (error) {
        showToast('Ingest failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

/* ------------------------ Bulk Scan + Batch Ingest ------------------------ */

let scanAlbums = [];
let selectedAlbumPaths = new Set();

function updateRunButtonState() {
    const btn = document.getElementById('run-ingest-btn');
    const selectedCountEl = document.getElementById('scan-selected-count');
    if (selectedCountEl) selectedCountEl.textContent = String(selectedAlbumPaths.size);

    if (btn) {
        btn.disabled = selectedAlbumPaths.size === 0;
    }
}

function getBool(val) {
    return val === true;
}

function coverDataUrl(album) {
    const b64 = album.cover_base64 || (album.album_art && album.album_art.cover_base64);
    if (!b64) return null;
    // We don't know image type; jpg works for most. The browser will still display many PNGs.
    return `data:image/jpeg;base64,${b64}`;
}

function renderScanTable() {
    const container = document.getElementById('scan-results');
    const tsEl = document.getElementById('scan-timestamp');
    const totalEl = document.getElementById('scan-total-count');

    if (!container) return;

    if (!scanAlbums || scanAlbums.length === 0) {
        container.innerHTML = '<div class="empty-state">No albums found in staging.</div>';
        if (totalEl) totalEl.textContent = '0';
        if (tsEl) tsEl.textContent = '—';
        updateRunButtonState();
        return;
    }

    if (totalEl) totalEl.textContent = String(scanAlbums.length);

    // Build table
    let html = '';
    html += '<table class="scan-table">';
    html += '<thead><tr>';
    html += '<th style="width:44px;">Pick</th>';
    html += '<th style="width:70px;">Cover</th>';
    html += '<th>Folder</th>';
    html += '<th>Album / Artist</th>';
    html += '<th>Genre</th>';
    html += '<th style="width:70px;">Year</th>';
    html += '<th style="width:70px;">Tracks</th>';
    html += '<th style="width:90px;">Album Art</th>';
    html += '<th style="width:90px;">Artist Art</th>';
    html += '<th style="width:95px;">Confidence</th>';
    html += '</tr></thead>';
    html += '<tbody>';

    scanAlbums.forEach((a, idx) => {
        const path = a.path || '';
        const checked = selectedAlbumPaths.has(path) ? 'checked' : '';
        const coverUrl = coverDataUrl(a);
        const hasCover = getBool(a.has_cover || (a.album_art && a.album_art.has_cover));
        const artistExists = getBool(a.artist_img_exists || (a.artist_art && a.artist_art.artist_img_exists));
        const artistAvail = getBool(a.artist_art_available || (a.artist_art && a.artist_art.artist_art_available));

        const albumArtPill = hasCover ? '<span class="pill ok">OK</span>' : '<span class="pill bad">Missing</span>';
        const artistArtPill = artistExists ? '<span class="pill ok">Exists</span>' :
                              (artistAvail ? '<span class="pill warn">Avail</span>' : '<span class="pill bad">Missing</span>');

        const gStatus = a.genre_status || 'missing';
        const genrePill = gStatus === 'ok' ? '<span class="pill ok">OK</span>' :
                          (gStatus === 'nonstandard' ? '<span class="pill warn">Nonstd</span>' : '<span class="pill bad">Missing</span>');

        const conf = (a.confidence || 'unknown').toLowerCase();
        const confPill = conf === 'high' ? '<span class="pill ok">High</span>' :
                         (conf === 'medium' ? '<span class="pill warn">Medium</span>' :
                         (conf === 'low' ? '<span class="pill bad">Low</span>' : '<span class="pill">?</span>'));

        const title = escapeHtml(a.name || '');
        const albumArtist = escapeHtml(a.album_artist || '');
        const album = escapeHtml(a.album || '');
        const year = escapeHtml(a.year || '');
        const genre = escapeHtml(a.genre || '');
        const tracks = typeof a.track_count === 'number' ? a.track_count : '';

        const destPath = escapeHtml(a.dest_path || '');

        const reasons = Array.isArray(a.confidence_reasons) ? a.confidence_reasons : [];
        const tooltip = reasons.length ? escapeHtml(reasons.join(' | ')) : '';

        html += `<tr title="${tooltip}">`;
        html += `<td><input type="checkbox" data-path="${escapeHtml(path)}" ${checked} onchange="toggleScanSelection(this)"></td>`;
        html += `<td>${coverUrl ? `<img class="scan-cover" src="${coverUrl}" alt="cover">` : '<div class="scan-cover" style="display:flex;align-items:center;justify-content:center;color:var(--text-secondary);font-size:0.7rem;">—</div>'}</td>`;
        html += `<td><div>${title}</div><div class="mono">${escapeHtml(path)}</div></td>`;
        html += `<td><div><strong>${album || '—'}</strong></div><div style="color:var(--text-secondary);font-size:0.8rem;">${albumArtist || '—'}</div><div class="mono">${destPath}</div></td>`;
        html += `<td><div>${genre || '—'}</div><div style="margin-top:6px;">${genrePill}</div></td>`;
        html += `<td>${year || '—'}</td>`;
        html += `<td>${tracks}</td>`;
        html += `<td>${albumArtPill}</td>`;
        html += `<td>${artistArtPill}</td>`;
        html += `<td>${confPill}</td>`;
        html += '</tr>';
    });

    html += '</tbody></table>';

    container.innerHTML = html;
    updateRunButtonState();
}

function toggleScanSelection(checkboxEl) {
    const path = checkboxEl.getAttribute('data-path') || '';
    if (!path) return;
    if (checkboxEl.checked) {
        selectedAlbumPaths.add(path);
    } else {
        selectedAlbumPaths.delete(path);
    }
    updateRunButtonState();
}

async function scanSources() {
    showLoading();

    try {
        const data = await fetchAPI('/music/api/ingest/scan-sources');
        scanAlbums = data.albums || [];
        selectedAlbumPaths = new Set(); // reset selection on each scan
        if (document.getElementById('scan-timestamp')) {
            document.getElementById('scan-timestamp').textContent = data.scanned_at || '—';
        }
        renderScanTable();
        showToast(`Scan complete: ${scanAlbums.length} album(s)`, 'success');
    } catch (error) {
        showToast('Scan failed: ' + error.message, 'error');
        const container = document.getElementById('scan-results');
        if (container) container.innerHTML = '<div class="empty-state">Scan failed. Check server console for details.</div>';
    } finally {
        hideLoading();
    }
}

function runSelectedIngest() {
    // Alias (button handler)
    return runSelectedIngestImpl();
}

async function runSelectedIngestImpl() {
    if (!scanAlbums || scanAlbums.length === 0) {
        showToast('No scan results. Click Scan Sources first.', 'warning');
        return;
    }
    if (selectedAlbumPaths.size === 0) {
        showToast('Select at least one album.', 'warning');
        return;
    }

    // Build payload from selected items using scan metadata (informational only)
    const selected = scanAlbums
        .filter(a => selectedAlbumPaths.has(a.path))
        .map(a => ({
            path: a.path,
            album_artist: a.album_artist || '',
            album: a.album || '',
            year: a.year || ''
        }));

    showLoading();

    try {
        const data = await fetchAPI('/music/api/ingest/run-batch', {
            method: 'POST',
            body: JSON.stringify({ items: selected })
        });

        const ok = data.ok || 0;
        const failed = data.failed || 0;

        if (failed === 0) {
            showToast(`Ingest complete: ${ok} succeeded`, 'success');
        } else {
            showToast(`Ingest finished: ${ok} ok, ${failed} failed (see console)`, 'warning');
            console.warn('Batch ingest results:', data);
        }

        // Re-scan to refresh table (items were cleaned up from staging)
        await scanSources();
    } catch (error) {
        showToast('Ingest failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Backward compatibility: keep old "loadAlbums" button working
// (legacy list and preview modal remain unchanged)

// Utility functions
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function formatDate(dateStr) {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
}

async function fetchAPI(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Request failed');
    }
    return response.json();
}

function showLoading() {
    document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}

function showToast(message, type = 'info') {
    // Simple toast implementation
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        padding: 12px 24px;
        background: ${type === 'success' ? '#4caf50' : type === 'error' ? '#f44336' : type === 'warning' ? '#ff9800' : '#2196f3'};
        color: white;
        border-radius: 4px;
        z-index: 10001;
        animation: slideIn 0.3s ease;
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Check URL for tab parameter
    const urlParams = new URLSearchParams(window.location.search);
    const tab = urlParams.get('tab');
    if (tab) {
        switchTab(tab);
    }
    
    // Enter key on search input
    const searchInput = document.getElementById('search-query');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchMusic();
            }
        });
    }
});