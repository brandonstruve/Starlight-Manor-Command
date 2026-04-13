document.addEventListener('DOMContentLoaded', () => {
    let catalogData = {};
    let currentPayload = null;
    let currentRow = null;

    const scanBtn = document.getElementById('scanBtn');
    const videoBody = document.getElementById('videoBody');
    const noFilesMsg = document.getElementById('noFilesMsg');
    const modal = document.getElementById('previewModal');
    const confirmBtn = document.getElementById('confirmPublish');

    // Fetch the Genre/Album mapping from the CSV via the API
    fetch('/api/catalog')
        .then(res => res.json())
        .then(data => { catalogData = data; });

    // Handle Folder Scanning
    scanBtn.addEventListener('click', () => {
        fetch('/api/scan')
            .then(res => res.json())
            .then(files => {
                videoBody.innerHTML = '';
                if (files.length > 0) {
                    noFilesMsg.style.display = 'none';
                    files.forEach(file => addRow(file));
                } else {
                    noFilesMsg.style.display = 'block';
                }
            });
    });

    function addRow(filename) {
        const tr = document.createElement('tr');
        const genres = Object.keys(catalogData);
        const genreOptions = genres.map(g => `<option value="${g}">${g}</option>`).join('');

        tr.innerHTML = `
            <td style="font-size: 0.75rem; opacity: 0.6;">${filename}</td>
            <td><input type="text" class="v-title" value="${filename.split('.')[0]}"></td>
            <td><input type="number" class="v-year" value="${new Date().getFullYear()}"></td>
            <td>
                <select class="v-genre"><option value="">Genre...</option>${genreOptions}</select>
                <select class="v-album" style="margin-top:5px;"><option value="">Album...</option></select>
            </td>
            <td>
                <button class="btn btn-secondary preview-btn">Preview</button>
            </td>
        `;

        const genreSelect = tr.querySelector('.v-genre');
        const albumSelect = tr.querySelector('.v-album');

        // Update Album dropdown when Genre changes
        genreSelect.addEventListener('change', () => {
            const albums = catalogData[genreSelect.value] || [];
            albumSelect.innerHTML = '<option value="">Album...</option>' + 
                albums.map(a => `<option value="${a}">${a}</option>`).join('');
        });

        // Trigger Preview Modal
        tr.querySelector('.preview-btn').addEventListener('click', () => {
            const title = tr.querySelector('.v-title').value;
            const album = albumSelect.value;
            const genre = genreSelect.value;
            const year = tr.querySelector('.v-year').value;
            
            if(!genre || !album) return alert("Please select a Genre and Album first.");

            // Store current data for publishing
            currentPayload = {
                filename: filename,
                title: title,
                year: year,
                genre: genre,
                album: album,
                description: "" 
            };
            currentRow = tr;

            // 1. Set the Destination Path Preview
            const destPath = `\\\\SM-NAS-01\\Media\\Home Media\\${genre} - ${album} - ${title}\\${genre} - ${album} - ${title}.mp4`;
            document.getElementById('prePath').innerText = destPath;
            
            // 2. Load Artwork with clean error handling
            // This uses the /working/ route defined in app.py
            const artBase = `/working/Home Videos/Art`; 
            const timeStamp = new Date().getTime(); // Prevent browser caching

            const loadArt = (containerId, type, fallback) => {
                const container = document.getElementById(containerId);
                const imgSrc = `${artBase}/${type}/${album}.jpg?t=${timeStamp}`;
                
                // Clear existing content and set image with an onerror fallback
                container.innerHTML = `<img src="${imgSrc}" 
                    onerror="this.outerHTML='<div class=\"art-error\">${fallback}</div>'">`;
            };

            loadArt('posterPreview', 'Posters', 'No Poster Found');
            loadArt('bgPreview', 'Backgrounds', 'No Background Found');
            
            modal.style.display = 'flex';
        });

        videoBody.appendChild(tr);
    }

    // Final Publish Action
    confirmBtn.addEventListener('click', () => {
        confirmBtn.disabled = true;
        confirmBtn.innerText = "Processing...";

        fetch('/api/publish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentPayload)
        })
        .then(res => res.json())
        .then(data => {
            if(data.status === 'success') {
                currentRow.remove();
                closeModal();
                if (videoBody.children.length === 0) noFilesMsg.style.display = 'block';
            } else {
                alert("Error: " + data.message);
            }
        })
        .finally(() => {
            confirmBtn.disabled = false;
            confirmBtn.innerText = "Confirm & Publish";
        });
    });
});

function closeModal() {
    document.getElementById('previewModal').style.display = 'none';
}