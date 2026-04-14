// Photos Module JavaScript

// Ingest Preflight
async function ingestPreflight() {
    showLoading();

    try {
        const data = await fetchAPI('/photos/api/ingest/preflight?details=1');

        const resultsDiv = document.getElementById('ingest-results');
        resultsDiv.classList.add('show');

        let html = '<h4>Ingest Preview</h4>';
        html += '<div class="result-success">';
        html += `<p>✅ ${data.counts.to_intake} files → Intake</p>`;
        html += `<p>⚠️ ${data.counts.to_needsgps} files → NeedsGPS</p>`;
        html += `<p>⏭️ ${data.counts.skip_duplicate} duplicates (skipped)</p>`;
        if (data.counts.errors > 0) {
            html += `<p class="result-error">❌ ${data.counts.errors} errors</p>`;
        }
        html += '</div>';

        if (data.samples.to_intake && data.samples.to_intake.length > 0) {
            html += '<h5>Sample Files to Intake (showing first 5):</h5>';
            html += '<ul>';
            data.samples.to_intake.slice(0, 5).forEach(item => {
                const filename = item.src_path.split('\\').pop();
                html += `<li>${filename}</li>`;
            });
            html += '</ul>';
        }

        if (data.samples.to_needsgps && data.samples.to_needsgps.length > 0) {
            html += '<h5>Sample Files to NeedsGPS (showing first 5):</h5>';
            html += '<ul>';
            data.samples.to_needsgps.slice(0, 5).forEach(item => {
                const filename = item.src_path.split('\\').pop();
                html += `<li>${filename} - ${item.reason}</li>`;
            });
            html += '</ul>';
        }

        html += `<p style="margin-top: 16px;"><small>Manifest will be saved to: ${data.manifest_hint}</small></p>`;

        resultsDiv.innerHTML = html;

        showToast('Scan complete', 'success');
    } catch (error) {
        showToast('Scan failed: ' + error.message, 'error');
        document.getElementById('ingest-results').classList.remove('show');
    } finally {
        hideLoading();
    }
}

// Ingest Run
async function ingestRun() {
    if (!confirm('This will move photos from Raw Import to working folders. Continue?')) {
        return;
    }

    showLoading();

    try {
        const data = await fetchAPI('/photos/api/ingest/run', {
            method: 'POST'
        });

        const resultsDiv = document.getElementById('ingest-results');
        resultsDiv.classList.add('show');

        let html = '<h4>Ingest Complete</h4>';
        if (data.status === 'success') {
            html += '<div class="result-success">';
            html += `<p>✅ ${data.message}</p>`;
            html += '</div>';
        } else {
            html += '<div class="result-error">';
            html += `<p>❌ ${data.message}</p>`;
            html += '</div>';
        }

        resultsDiv.innerHTML = html;

        showToast(data.message, data.status === 'success' ? 'success' : 'error');
    } catch (error) {
        showToast('Ingest failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Publish Preflight
async function publishPreflight() {
    showLoading();

    try {
        const data = await fetchAPI('/photos/api/publish/preflight');

        const resultsDiv = document.getElementById('publish-results');
        resultsDiv.classList.add('show');

        const counts = data.counts || { total: 0, ready: 0, skipped: 0, conflicts: 0 };
        const rows = data.rows || [];

        let html = '<h4>Publish Preview</h4>';

        html += '<div class="result-success">';
        html += `<p>Total scanned: <strong>${counts.total}</strong></p>`;
        html += `<p>✅ Ready: <strong>${counts.ready}</strong></p>`;
        html += `<p>⚠️ Skipped: <strong>${counts.skipped}</strong></p>`;
        html += `<p>❌ Conflicts: <strong>${counts.conflicts}</strong></p>`;
        html += '</div>';

        if (counts.skipped > 0 || counts.conflicts > 0) {
            html += '<div class="result-warning" style="margin-top: 12px;">';
            html += '<p><strong>Not everything is publishable yet.</strong></p>';
            html += '<p>Fix missing GPS/date issues in digiKam, then re-run Preview.</p>';
            html += '</div>';
        }

        if (rows.length === 0) {
            html += '<p style="margin-top: 12px;">No files found in working publish folders.</p>';
            html += `<p style="margin-top: 12px;"><small>Scanning: ${(data.source_dirs || []).join(' , ')}</small></p>`;
            resultsDiv.innerHTML = html;
            showToast('Preview complete', 'success');
            return;
        }

        html += '<div style="margin-top: 14px; overflow-x: auto;">';
        html += '<table style="width: 100%; border-collapse: collapse;">';
        html += '<thead>';
        html += '<tr>';
        html += '<th style="text-align:left; padding:8px; border-bottom:1px solid #444;">Source File</th>';
        html += '<th style="text-align:left; padding:8px; border-bottom:1px solid #444;">New File Name</th>';
        html += '<th style="text-align:left; padding:8px; border-bottom:1px solid #444;">New Path</th>';
        html += '<th style="text-align:left; padding:8px; border-bottom:1px solid #444;">New Date</th>';
        html += '<th style="text-align:left; padding:8px; border-bottom:1px solid #444;">GPS</th>';
        html += '<th style="text-align:left; padding:8px; border-bottom:1px solid #444;">Status</th>';
        html += '<th style="text-align:left; padding:8px; border-bottom:1px solid #444;">Reason</th>';
        html += '</tr>';
        html += '</thead>';
        html += '<tbody>';

        rows.forEach(r => {
            const status = (r.status || '').toUpperCase();
            let rowStyle = 'border-bottom:1px solid #333;';
            if (status === 'READY') rowStyle += ' background: rgba(0, 128, 0, 0.08);';
            if (status === 'SKIP') rowStyle += ' background: rgba(255, 165, 0, 0.08);';
            if (status === 'CONFLICT') rowStyle += ' background: rgba(255, 0, 0, 0.10);';

            const gpsFlag = r.has_gps ? '✅' : '❌';

            // Friendly source display (filename), but keep full path accessible in title
            const sourceDisplay = r.source_file || (r.source_path ? r.source_path.split('\\').pop() : '');
            const sourceTitle = r.source_path || '';

            const newPath = r.library_dest || '';
            const uploadPath = r.upload_dest || '';

            html += `<tr style="${rowStyle}">`;
            html += `<td style="padding:8px;" title="${escapeHtml(sourceTitle)}">${escapeHtml(sourceDisplay)}</td>`;
            html += `<td style="padding:8px; font-family: monospace;">${escapeHtml(r.new_file_name || '')}</td>`;
            html += `<td style="padding:8px; font-family: monospace;">${escapeHtml(newPath)}<br><small>Upload copy: ${escapeHtml(uploadPath)}</small></td>`;
            html += `<td style="padding:8px; font-family: monospace;">${escapeHtml(r.new_date || '')}</td>`;
            html += `<td style="padding:8px;">${gpsFlag}</td>`;
            html += `<td style="padding:8px;"><strong>${escapeHtml(status)}</strong></td>`;
            html += `<td style="padding:8px;">${escapeHtml(r.reason || '')}</td>`;
            html += `</tr>`;
        });

        html += '</tbody>';
        html += '</table>';
        html += '</div>';

        html += `<p style="margin-top: 16px;"><small>Scanning: ${(data.source_dirs || []).join(' , ')}</small></p>`;

        resultsDiv.innerHTML = html;

        showToast('Preview complete', 'success');
    } catch (error) {
        showToast('Preview failed: ' + error.message, 'error');
        document.getElementById('publish-results').classList.remove('show');
    } finally {
        hideLoading();
    }
}

// Small HTML escaper to keep table safe
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

// Publish Run
async function publishRun() {
    if (!confirm('This will rename and move photos to final destinations. Continue?')) {
        return;
    }

    showLoading();

    try {
        const data = await fetchAPI('/photos/api/publish/run', {
            method: 'POST'
        });

        const resultsDiv = document.getElementById('publish-results');
        resultsDiv.classList.add('show');

        let html = '<h4>Publish Complete</h4>';
        if (data.status === 'success') {
            html += '<div class="result-success">';
            html += `<p>✅ ${data.message}</p>`;
            html += '<p>Files copied to:</p>';
            html += '<ul>';
            html += '<li>Upload Room</li>';
            html += '<li>Library (\\\\SM-NAS-01\\Media\\Photos\\)</li>';
            html += '</ul>';
            html += '</div>';
        } else {
            html += '<div class="result-error">';
            html += `<p>❌ ${data.message}</p>`;
            html += '</div>';
        }

        resultsDiv.innerHTML = html;

        showToast(data.message, data.status === 'success' ? 'success' : 'error');
    } catch (error) {
        showToast('Publish failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Cleanup
async function cleanup() {
    const confirmation = prompt('This will permanently delete files from working folders. Type "DELETE" to confirm:');

    if (confirmation !== 'DELETE') {
        showToast('Cleanup cancelled', 'info');
        return;
    }

    showLoading();

    try {
        const data = await fetchAPI('/photos/api/cleanup', {
            method: 'POST'
        });

        const resultsDiv = document.getElementById('cleanup-results');
        resultsDiv.classList.add('show');

        let html = '<h4>Cleanup Complete</h4>';
        if (data.status === 'success') {
            html += '<div class="result-success">';
            html += `<p>✅ ${data.message}</p>`;
            html += '</div>';
        } else {
            html += '<div class="result-error">';
            html += `<p>❌ ${data.message}</p>`;
            html += '</div>';
        }

        resultsDiv.innerHTML = html;

        showToast(data.message, data.status === 'success' ? 'success' : 'error');
    } catch (error) {
        showToast('Cleanup failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    console.log('Photos module initialized');
});
