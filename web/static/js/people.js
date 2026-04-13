let state = {
    activeTab: 'people', page: 1, totalPages: 1, category: '', subcategory: '',
    search: '', categoryMap: {}, currentPerson: null, isEditMode: false
};

document.addEventListener('DOMContentLoaded', () => { fetchDirectory(); });

// --- Master View & Navigation ---

function switchTab(tab) {
    state.activeTab = tab;
    document.getElementById('toggle-people-btn').className = tab === 'people' ? 'btn btn-primary' : 'btn btn-secondary';
    document.getElementById('toggle-households-btn').className = tab === 'households' ? 'btn btn-primary' : 'btn btn-secondary';
    document.getElementById('toggle-relationships-btn').className = tab === 'relationships' ? 'btn btn-primary' : 'btn btn-secondary';
    
    document.getElementById('people-grid').style.display = tab === 'people' ? 'grid' : 'none';
    document.getElementById('household-grid').style.display = tab === 'households' ? 'grid' : 'none';
    document.getElementById('relationship-grid').style.display = tab === 'relationships' ? 'grid' : 'none';
    
    document.getElementById('people-pagination').style.display = tab === 'people' ? 'flex' : 'none';
    
    if (tab === 'people') { fetchDirectory(); } 
    else if (tab === 'households') { fetchHouseholds(); }
    else if (tab === 'relationships') { fetchRelationships(); }
}

let searchTimeout;
function handleSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        state.search = document.getElementById('search-input').value;
        state.page = 1;
        if (state.activeTab === 'people') fetchDirectory();
    }, 300);
}

// --- Data Fetching & Rendering ---

async function fetchDirectory() {
    const url = `/people/api/people_list?page=${state.page}&category=${encodeURIComponent(state.category)}&subcategory=${encodeURIComponent(state.subcategory)}&search=${encodeURIComponent(state.search)}`;
    try {
        const res = await fetch(url);
        const data = await res.json();
        state.totalPages = data.total_pages;
        state.categoryMap = data.categories;
        updateFilterUI();
        renderGrid(data.records);
        document.getElementById('page-info').innerText = `Page ${data.page} of ${data.total_pages}`;
        document.getElementById('results-count').innerText = `${data.total} Results`;
        document.getElementById('btn-prev').disabled = state.page === 1;
        document.getElementById('btn-next').disabled = state.page === state.totalPages;
    } catch (err) { console.error("Failed to load directory", err); }
}

async function fetchHouseholds() {
    try {
        const res = await fetch('/people/api/households');
        const households = await res.json();
        renderHouseholdGrid(households);
        document.getElementById('results-count').innerText = `${households.length} Households`;
    } catch (err) { console.error("Failed to load households", err); }
}

async function fetchRelationships() {
    try {
        const res = await fetch('/people/api/relationships_list');
        const rels = await res.json();
        renderRelationshipGrid(rels);
        document.getElementById('results-count').innerText = `${rels.length} Marriages`;
    } catch (err) { console.error("Failed to load relationships", err); }
}

function renderGrid(records) {
    const grid = document.getElementById('people-grid');
    grid.innerHTML = '';
    records.forEach(person => {
        const card = document.createElement('div');
        card.className = 'person-card';
        if (person.I_Immich_ID) { card.onclick = () => loadProfile(person.I_Immich_ID); }
        let avatarHtml = person.ProfilePhotoPath 
            ? `<img src="/people/api/profile_photo?path=${encodeURIComponent(person.ProfilePhotoPath)}" class="card-avatar" onerror="this.style.display='none'">`
            : `<div class="card-initials">${getInitials(person.Name)}</div>`;
        card.innerHTML = `
            <div class="card-header-flex">${avatarHtml}
                <div class="card-primary-info"><h3>${person.Name}</h3></div>
            </div>
            <div class="card-meta"><span>${person.D_Category || 'Uncategorized'}</span>${person['D_Sub Category'] ? `<span> • ${person['D_Sub Category']}</span>` : ''}</div>`;
        grid.appendChild(card);
    });
}

function renderHouseholdGrid(households) {
    const grid = document.getElementById('household-grid');
    grid.innerHTML = '';
    households.forEach(hh => {
        const card = document.createElement('div');
        card.className = 'household-card';
        let addressHtml = '';
        if (hh.street_address && hh.city && hh.state) {
            addressHtml = `<div class="address-line">${hh.street_address}, ${hh.city}, ${hh.state}</div>`;
        }
        card.innerHTML = `
            <h3>${hh.household_name}</h3>
            <div class="card-meta" style="margin-top: 10px;"><strong>Residents:</strong> ${hh.residents || 'Empty'}</div>
            ${addressHtml}
        `;
        grid.appendChild(card);
    });
}

function renderRelationshipGrid(rels) {
    const grid = document.getElementById('relationship-grid');
    grid.innerHTML = '';
    rels.forEach(rel => {
        const card = document.createElement('div');
        card.className = 'relationship-card';
        const yearsString = calculateYearsTogether(rel.anniversary_date);
        card.innerHTML = `
            <h3 style="margin-bottom: 2px;">${rel.person_a_name}</h3>
            <h3 style="margin-top: 0; color: var(--text-muted); font-weight: normal;">& ${rel.person_b_name}</h3>
            <div class="card-meta" style="margin-top: 15px;"><strong>Est.</strong> ${rel.anniversary_date || 'Unknown'}</div>
            ${yearsString ? `<div class="years-badge">${yearsString}</div>` : ''}
        `;
        grid.appendChild(card);
    });
}

function calculateYearsTogether(dateString) {
    if (!dateString) return null;
    const start = new Date(dateString);
    const today = new Date();
    let years = today.getFullYear() - start.getFullYear();
    const m = today.getMonth() - start.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < start.getDate())) {
        years--;
    }
    return years >= 0 ? `${years} Years` : null;
}

function updateFilterUI() {
    const catSelect = document.getElementById('category-filter');
    const subSelect = document.getElementById('subcategory-filter');
    if (catSelect.options.length <= 1) {
        Object.keys(state.categoryMap).forEach(cat => {
            const opt = document.createElement('option'); opt.value = cat; opt.text = cat;
            if (cat === state.category) opt.selected = true;
            catSelect.appendChild(opt);
        });
    }
    subSelect.innerHTML = '<option value="">All Sub-Categories</option>';
    if (state.category && state.categoryMap[state.category]) {
        subSelect.disabled = false;
        state.categoryMap[state.category].forEach(sub => {
            const opt = document.createElement('option'); opt.value = sub; opt.text = sub;
            if (sub === state.subcategory) opt.selected = true;
            subSelect.appendChild(opt);
        });
    } else { subSelect.disabled = true; state.subcategory = ''; }
}

// --- Dossier Profile Logic ---

async function loadProfile(immichId) {
    state.isEditMode = false;
    document.getElementById('master-view').style.display = 'none';
    document.getElementById('detail-view').style.display = 'block';
    
    try {
        const res = await fetch(`/people/api/person/${immichId}`);
        state.currentPerson = await res.json();
        const p = state.currentPerson;
        
        // Header
        document.getElementById('profile-name').innerText = p.Name;
        
        // Column 1: About
        document.getElementById('val-dob').innerText = p.I_Birthdate || 'N/A';
        document.getElementById('val-dod').innerText = p.I_DeathDate || 'N/A';
        document.getElementById('dod-row').style.display = (p.I_DeathDate && p.I_DeathDate !== 'N/A') ? 'block' : 'none';
        
        // Column 2: Contact
        document.getElementById('val-email').innerText = p.Email || 'N/A';
        document.getElementById('val-phone').innerText = p.Phone || 'N/A';
        document.getElementById('val-address').innerText = p.Address || 'N/A';
        
        // Column 3: Classification / Relational
        document.getElementById('val-category').innerText = p.D_Category || 'N/A';
        document.getElementById('val-subcategory').innerText = p['D_Sub Category'] || 'N/A';
        
        document.getElementById('val-household').innerText = p.Household_Name || 'Standalone';
        document.getElementById('btn-add-household').style.display = 'inline-block';
        
        document.getElementById('val-spouse').innerText = p.Spouse_Name || 'None';
        document.getElementById('btn-add-spouse').style.display = p.Spouse_Name ? 'none' : 'inline-block';
        
        const annivRow = document.getElementById('anniversary-row');
        if (p.Anniversary_Date) {
            document.getElementById('val-anniversary').innerText = p.Anniversary_Date;
            annivRow.style.display = 'block';
        } else {
            annivRow.style.display = 'none';
        }

        // Media Section
        document.getElementById('val-assets-count').innerText = p.ImmichAssetCount || '0';
        if (p.random_asset_id) {
            document.getElementById('featured-image').src = `/people/api/image/${p.random_asset_id}`;
            document.getElementById('featured-caption').innerText = `Archive Photo of ${p.first_name}`;
        }
        document.getElementById('link-all-photos').href = p.I_Immich_ID ? `http://192.168.68.163:2283/people/${p.I_Immich_ID}` : '#';

        // Footer System Data
        document.getElementById('val-google-id').innerText = p.G_Google_ID || 'N/A';
        document.getElementById('val-immich-id').innerText = p.I_Immich_ID || 'N/A';
        document.getElementById('val-digikam-id').innerText = p.D_digiKam_ID || 'N/A';
        
        // Avatar
        const imgEl = document.getElementById('profile-avatar');
        const initEl = document.getElementById('profile-initials');
        if (p.ProfilePhotoPath) {
            imgEl.src = `/people/api/profile_photo?path=${encodeURIComponent(p.ProfilePhotoPath)}`;
            imgEl.style.display = 'block'; initEl.style.display = 'none';
        } else {
            imgEl.style.display = 'none'; initEl.style.display = 'flex';
            initEl.innerText = getInitials(p.Name);
        }

        updateEditUI();
    } catch (err) { console.error(err); }
}

async function refreshRandomImage() {
    if (!state.currentPerson || !state.currentPerson.I_Immich_ID) return;
    try {
        const res = await fetch(`/people/api/person/${state.currentPerson.I_Immich_ID}`);
        const data = await res.json();
        if (data.random_asset_id) {
            document.getElementById('featured-image').src = `/people/api/image/${data.random_asset_id}`;
            document.getElementById('featured-caption').innerText = `New Archive Photo of ${data.first_name}`;
        }
    } catch (err) { console.error("Failed to refresh image", err); }
}

// --- Editing Logic ---

function toggleEditMode() {
    state.isEditMode = !state.isEditMode;
    updateEditUI();
}

function updateEditUI() {
    const editBtn = document.getElementById('edit-btn');
    const saveBtn = document.getElementById('save-btn');
    const dodRow = document.getElementById('dod-row');
    
    if (state.isEditMode) {
        editBtn.innerText = "Cancel";
        editBtn.classList.replace('btn-primary', 'btn-secondary');
        saveBtn.style.display = "inline-block";
        dodRow.style.display = 'block';
    } else {
        editBtn.innerText = "Edit";
        editBtn.classList.replace('btn-secondary', 'btn-primary');
        saveBtn.style.display = "none";
        if (state.currentPerson && (!state.currentPerson.I_DeathDate || state.currentPerson.I_DeathDate === 'N/A')) {
            dodRow.style.display = 'none';
        }
    }

    document.querySelectorAll('.editable').forEach(el => {
        const field = el.getAttribute('data-field');
        if (state.isEditMode) {
            const val = el.innerText === 'N/A' ? '' : el.innerText;
            el.innerHTML = `<input type="text" id="edit-${field}" value="${val}" class="edit-input" style="width: 100%; padding: 4px;">`;
        } else {
            el.innerText = state.currentPerson ? state.currentPerson[getFieldKey(field)] || 'N/A' : 'N/A';
        }
    });

    const addrSpan = document.getElementById('val-address');
    const addrEdit = document.getElementById('address-edit-fields');
    if (state.isEditMode) {
        addrSpan.style.display = 'none';
        addrEdit.style.display = 'flex';
        document.getElementById('edit-street').value = state.currentPerson.street_address || '';
        document.getElementById('edit-city').value = state.currentPerson.city || '';
        document.getElementById('edit-state').value = state.currentPerson.state || '';
        document.getElementById('edit-zip').value = state.currentPerson.zip_code || '';
    } else {
        addrSpan.style.display = 'inline';
        addrEdit.style.display = 'none';
    }
}

function getFieldKey(field) {
    const maps = { 
        'birthdate': 'I_Birthdate', 'deathdate': 'I_DeathDate', 'email': 'Email', 'phone': 'Phone',
        'category': 'D_Category', 'sub_category': 'D_Sub Category',
        'google_id': 'G_Google_ID', 'immich_id': 'I_Immich_ID', 'digikam_id': 'D_digiKam_ID'
    };
    return maps[field] || field;
}

async function saveProfile() {
    const payload = {
        immich_id: state.currentPerson.I_Immich_ID,
        birthdate: document.getElementById('edit-birthdate').value,
        deathdate: document.getElementById('edit-deathdate').value,
        email: document.getElementById('edit-email').value,
        phone: document.getElementById('edit-phone').value,
        street_address: document.getElementById('edit-street').value,
        city: document.getElementById('edit-city').value,
        state: document.getElementById('edit-state').value,
        zip_code: document.getElementById('edit-zip').value,
        category: document.getElementById('edit-category').value,
        sub_category: document.getElementById('edit-sub_category').value,
        google_id: document.getElementById('edit-google_id').value,
        digikam_id: document.getElementById('edit-digikam_id').value
    };

    try {
        const res = await fetch('/people/api/update_person', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            await loadProfile(state.currentPerson.I_Immich_ID);
            if (state.activeTab === 'people') fetchDirectory();
        }
    } catch (err) { console.error(err); }
}

// --- Modals & CRM Workflows ---

function closeModals() {
    document.getElementById('household-modal').style.display = 'none';
    document.getElementById('spouse-modal').style.display = 'none';
}

async function openHouseholdModal() {
    document.getElementById('household-modal').style.display = 'flex';
    switchHouseholdTab('existing');
    
    try {
        const res = await fetch('/people/api/households');
        const households = await res.json();
        const select = document.getElementById('household-select');
        select.innerHTML = '<option value="">-- Select a Household --</option>';
        households.forEach(hh => {
            select.innerHTML += `<option value="${hh.id}">${hh.household_name} (${hh.residents || 'Empty'})</option>`;
        });
    } catch (err) { console.error(err); }
}

function switchHouseholdTab(tab) {
    if (tab === 'existing') {
        document.getElementById('tab-existing').style.display = 'block';
        document.getElementById('tab-new').style.display = 'none';
        document.querySelectorAll('.tab-btn')[0].classList.add('active');
        document.querySelectorAll('.tab-btn')[1].classList.remove('active');
    } else {
        document.getElementById('tab-existing').style.display = 'none';
        document.getElementById('tab-new').style.display = 'block';
        document.querySelectorAll('.tab-btn')[0].classList.remove('active');
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
    }
}

async function submitHouseholdAssignment() {
    const hhId = document.getElementById('household-select').value;
    if (!hhId) return alert("Please select a household.");
    
    try {
        await fetch('/people/api/households/assign', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ immich_id: state.currentPerson.I_Immich_ID, household_id: hhId })
        });
        closeModals();
        loadProfile(state.currentPerson.I_Immich_ID);
    } catch (err) { console.error(err); }
}

async function createNewHousehold() {
    const name = document.getElementById('new-household-name').value;
    if (!name) return alert("Please provide a name for the new household.");
    
    try {
        await fetch('/people/api/households/create_and_batch', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name: name, person_ids: [state.currentPerson.I_Immich_ID] })
        });
        closeModals();
        loadProfile(state.currentPerson.I_Immich_ID);
    } catch (err) { console.error(err); }
}

async function openSpouseModal() {
    document.getElementById('spouse-modal').style.display = 'flex';
    try {
        const res = await fetch('/people/api/people_list?page=1'); 
        const data = await res.json();
        const select = document.getElementById('spouse-select');
        select.innerHTML = '<option value="">-- Select a Spouse --</option>';
        data.records.forEach(p => {
            if (p.I_Immich_ID !== state.currentPerson.I_Immich_ID && p.I_Immich_ID) {
                select.innerHTML += `<option value="${p.I_Immich_ID}">${p.Name}</option>`;
            }
        });
    } catch (err) { console.error(err); }
}

async function submitSpouseLink() {
    const spouseId = document.getElementById('spouse-select').value;
    const annivDate = document.getElementById('anniversary-input').value;
    
    if (!spouseId || !annivDate) return alert("Please select a spouse and provide an anniversary date.");
    
    try {
        const res = await fetch('/people/api/relationships/link', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                person1_id: state.currentPerson.I_Immich_ID, 
                person2_id: spouseId, 
                anniversary_date: annivDate 
            })
        });
        
        const json = await res.json();
        if (json.error) {
            alert(json.error);
        } else {
            closeModals();
            loadProfile(state.currentPerson.I_Immich_ID);
        }
    } catch (err) { console.error(err); }
}

// --- Utilities ---
function handleCategoryChange() { state.category = document.getElementById('category-filter').value; state.subcategory = ''; state.page = 1; fetchDirectory(); }
function handleSubCategoryChange() { state.subcategory = document.getElementById('subcategory-filter').value; state.page = 1; fetchDirectory(); }
function changePage(direction) { state.page += direction; fetchDirectory(); }
function closeProfile() { document.getElementById('detail-view').style.display = 'none'; document.getElementById('master-view').style.display = 'block'; }
function getInitials(name) { if (!name) return '?'; return name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase(); }