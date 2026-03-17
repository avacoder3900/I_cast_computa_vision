/**
 * Project detail page — tabs, import, labels, train, test, review, integrate.
 * Globals: PROJECT_ID, PROJECT_DATA (set in template).
 */

const BIMS_PHASES = [
    'backing', 'wax_filled', 'wax_qc', 'wax_stored', 'reagent_filled',
    'inspected', 'sealed', 'cured', 'stored', 'released', 'shipped',
    'assay_loaded', 'testing', 'completed', 'voided',
];

// State
let testFile = null;

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
    setupDragDrop();
    loadStats();
    loadImportGallery();
    renderPhaseLabels();
    renderCustomLabels();
    loadTrainingImages();
});

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.toggle('active', panel.id === `tab-${tabId}`);
    });

    // Refresh data when switching tabs
    if (tabId === 'import') loadImportGallery();
    if (tabId === 'train') { loadTrainingStats(); loadTrainingImages(); }
    if (tabId === 'review') loadReviewImages();
}

// ---------------------------------------------------------------------------
// Stats sidebar
// ---------------------------------------------------------------------------

async function loadStats() {
    try {
        const stats = await API.get(`/api/v1/projects/${PROJECT_ID}/stats`);
        updateSidebar(stats);
    } catch (err) {
        console.error('Failed to load stats:', err);
    }
}

function updateSidebar(stats) {
    const total = stats.image_count || 0;
    const annotated = stats.annotated_count || 0;
    const approved = stats.approved_count || 0;
    const rejected = stats.rejected_count || 0;
    const accuracy = stats.accuracy || 0;

    document.getElementById('stat-annotations').textContent = `${annotated} of ${total}`;
    const annPct = total > 0 ? (annotated / total * 100) : 0;
    document.getElementById('annotations-bar').style.width = annPct + '%';

    document.getElementById('stat-accuracy').textContent = accuracy + '%';
    document.getElementById('accuracy-bar').style.width = accuracy + '%';

    const appPct = total > 0 ? (approved / total * 100) : 0;
    document.getElementById('stat-approved').textContent = `${approved} (${appPct.toFixed(0)}%)`;
    document.getElementById('approved-bar').style.width = appPct + '%';

    const rejPct = total > 0 ? (rejected / total * 100) : 0;
    document.getElementById('stat-rejected').textContent = `${rejected} (${rejPct.toFixed(0)}%)`;
    document.getElementById('rejected-bar').style.width = rejPct + '%';

    document.getElementById('stat-model-status').textContent = stats.model_status || 'untrained';

    // Update training counts
    if (document.getElementById('train-good-count')) {
        document.getElementById('train-good-count').textContent = stats.training_good || 0;
        document.getElementById('train-defect-count').textContent = stats.training_defect || 0;
        document.getElementById('train-uncat-count').textContent = stats.training_uncategorized || 0;
    }
}

// ---------------------------------------------------------------------------
// Import tab
// ---------------------------------------------------------------------------

function setupDragDrop() {
    const dropzone = document.getElementById('import-dropzone');
    if (!dropzone) return;

    ['dragenter', 'dragover'].forEach(evt => {
        dropzone.addEventListener(evt, e => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(evt => {
        dropzone.addEventListener(evt, e => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', e => {
        const files = e.dataTransfer.files;
        if (files.length) handleImportFiles(files);
    });

    // Test dropzone too
    const testDrop = document.getElementById('test-dropzone');
    if (testDrop) {
        ['dragenter', 'dragover'].forEach(evt => {
            testDrop.addEventListener(evt, e => {
                e.preventDefault();
                testDrop.classList.add('dragover');
            });
        });
        ['dragleave', 'drop'].forEach(evt => {
            testDrop.addEventListener(evt, e => {
                e.preventDefault();
                testDrop.classList.remove('dragover');
            });
        });
        testDrop.addEventListener('drop', e => {
            if (e.dataTransfer.files.length) handleTestFile(e.dataTransfer.files[0]);
        });
    }
}

async function handleImportFiles(files) {
    const category = document.getElementById('import-category').value;
    const progressSection = document.getElementById('import-progress');
    const progressBar = document.getElementById('import-progress-bar');
    const statusText = document.getElementById('import-status-text');

    progressSection.style.display = 'block';
    const total = files.length;
    let done = 0;

    for (const file of files) {
        statusText.textContent = `Uploading ${file.name} (${done + 1}/${total})...`;
        try {
            const fd = new FormData();
            fd.append('file', file);
            fd.append('category', category);
            await API.upload(`/api/v1/projects/${PROJECT_ID}/training/upload`, fd);
        } catch (err) {
            console.error(`Failed to upload ${file.name}:`, err);
        }
        done++;
        const pct = Math.round(done / total * 100);
        progressBar.style.width = pct + '%';
        progressBar.textContent = pct + '%';
    }

    statusText.textContent = `Uploaded ${done} of ${total} images.`;
    setTimeout(() => { progressSection.style.display = 'none'; }, 2000);

    loadImportGallery();
    loadStats();
}

async function loadImportGallery() {
    try {
        const data = await API.get(`/api/v1/projects/${PROJECT_ID}/training/images`, { limit: 100 });
        renderImportGallery(data.images || []);
    } catch (err) {
        console.error('Failed to load import gallery:', err);
    }
}

function renderImportGallery(images) {
    const gallery = document.getElementById('import-gallery');
    if (!images.length) {
        gallery.innerHTML = '<div class="empty-state"><p>No images uploaded yet.</p></div>';
        return;
    }
    gallery.innerHTML = images.map(img => `
        <div class="gallery-item">
            <span class="gallery-item-label ${img.category === 'good' ? 'good' : img.category === 'defect' ? 'defect' : ''}">${img.category}</span>
            <img src="${img.file_url}" alt="${img.filename}" loading="lazy">
            <div class="caption">
                <div class="caption-filename">${img.filename}</div>
            </div>
        </div>
    `).join('');
}

// ---------------------------------------------------------------------------
// Labels tab
// ---------------------------------------------------------------------------

function renderPhaseLabels() {
    const container = document.getElementById('phase-labels-list');
    if (!container) return;
    const projectPhases = PROJECT_DATA.phases || [];
    container.innerHTML = BIMS_PHASES.map(p => {
        const active = projectPhases.includes(p) ? 'active' : '';
        return `<span class="phase-label-chip ${active}" onclick="togglePhase('${p}', this)">${p.replace(/_/g, ' ')}</span>`;
    }).join('');
}

async function togglePhase(phase, el) {
    const phases = new Set(PROJECT_DATA.phases || []);
    if (phases.has(phase)) {
        phases.delete(phase);
        el.classList.remove('active');
    } else {
        phases.add(phase);
        el.classList.add('active');
    }
    PROJECT_DATA.phases = [...phases];
    try {
        await API.patch(`/api/v1/projects/${PROJECT_ID}`, { phases: PROJECT_DATA.phases });
    } catch (err) {
        showToast('Failed to update phases: ' + err.message, true);
    }
}

function renderCustomLabels() {
    const container = document.getElementById('custom-labels-list');
    if (!container) return;
    const labels = PROJECT_DATA.labels || [];
    if (!labels.length) {
        container.innerHTML = '<span class="text-muted" style="font-size:0.8rem;">No custom labels yet.</span>';
        return;
    }
    container.innerHTML = labels.map((l, i) => `
        <span class="custom-label-chip">
            <span class="custom-label-color" style="background:${l.color}"></span>
            ${l.name}
            <span style="cursor:pointer;opacity:0.5;margin-left:0.3rem;" onclick="removeCustomLabel(${i})">&times;</span>
        </span>
    `).join('');
}

async function addCustomLabel() {
    const nameInput = document.getElementById('new-label-name');
    const colorInput = document.getElementById('new-label-color');
    const name = nameInput.value.trim();
    const color = colorInput.value;
    if (!name) return;

    const labels = [...(PROJECT_DATA.labels || []), { name, color }];
    try {
        await API.patch(`/api/v1/projects/${PROJECT_ID}`, { labels });
        PROJECT_DATA.labels = labels;
        nameInput.value = '';
        renderCustomLabels();
    } catch (err) {
        showToast('Failed to add label: ' + err.message, true);
    }
}

async function removeCustomLabel(index) {
    const labels = [...(PROJECT_DATA.labels || [])];
    labels.splice(index, 1);
    try {
        await API.patch(`/api/v1/projects/${PROJECT_ID}`, { labels });
        PROJECT_DATA.labels = labels;
        renderCustomLabels();
    } catch (err) {
        showToast('Failed to remove label: ' + err.message, true);
    }
}

// ---------------------------------------------------------------------------
// Train tab
// ---------------------------------------------------------------------------

async function loadTrainingStats() {
    try {
        const data = await API.get(`/api/v1/projects/${PROJECT_ID}/training/data-stats`);
        document.getElementById('train-good-count').textContent = data.good_count;
        document.getElementById('train-defect-count').textContent = data.defect_count;
        document.getElementById('train-uncat-count').textContent = data.uncategorized_count;
    } catch (err) {
        console.error('Failed to load training stats:', err);
    }
}

async function loadTrainingImages() {
    const filter = document.getElementById('train-category-filter');
    const category = filter ? filter.value : '';
    const params = { limit: 100 };
    if (category) params.category = category;

    try {
        const data = await API.get(`/api/v1/projects/${PROJECT_ID}/training/images`, params);
        renderTrainGallery(data.images || []);
    } catch (err) {
        console.error('Failed to load training images:', err);
    }
}

function renderTrainGallery(images) {
    const gallery = document.getElementById('train-gallery');
    if (!images.length) {
        gallery.innerHTML = '<div class="empty-state"><p>No training images yet. Import some images first.</p></div>';
        return;
    }
    gallery.innerHTML = images.map(img => `
        <div class="gallery-item">
            <span class="gallery-item-label ${img.category === 'good' ? 'good' : img.category === 'defect' ? 'defect' : ''}">${img.category}</span>
            <img src="${img.file_url}" alt="${img.filename}" loading="lazy">
            <div class="caption">
                <div class="caption-filename">${img.filename}</div>
                <div class="caption-actions">
                    <select class="inline-category" data-filename="${img.filename}" onchange="recategorizeTrainImage('${img.filename}', this.value)">
                        <option value="good" ${img.category === 'good' ? 'selected' : ''}>Approved</option>
                        <option value="defect" ${img.category === 'defect' ? 'selected' : ''}>Rejected</option>
                        <option value="uncategorized" ${img.category === 'uncategorized' ? 'selected' : ''}>Unlabeled</option>
                    </select>
                </div>
            </div>
        </div>
    `).join('');
}

async function recategorizeTrainImage(filename, newCategory) {
    try {
        await API.patch(`/api/v1/projects/${PROJECT_ID}/training/images/${filename}`, { new_category: newCategory });
        loadTrainingStats();
        loadTrainingImages();
        loadStats();
    } catch (err) {
        showToast('Failed to recategorize: ' + err.message, true);
    }
}

async function startProjectTraining() {
    const btn = document.getElementById('start-train-btn');
    btn.disabled = true;
    btn.textContent = 'Training...';

    const progressSection = document.getElementById('training-progress-section');
    progressSection.style.display = 'block';

    try {
        await API.post(`/api/v1/projects/${PROJECT_ID}/training/start`);
        pollTrainingStatus();
    } catch (err) {
        showToast('Failed to start training: ' + err.message, true);
        btn.disabled = false;
        btn.textContent = 'Start Training';
    }
}

async function pollTrainingStatus() {
    const bar = document.getElementById('train-progress-bar');
    const text = document.getElementById('train-status-text');
    const btn = document.getElementById('start-train-btn');
    const log = document.getElementById('train-log');

    try {
        const status = await API.get(`/api/v1/projects/${PROJECT_ID}/training/status`);
        bar.style.width = (status.progress || 0) + '%';
        bar.textContent = (status.progress || 0) + '%';
        text.textContent = status.message || status.status;

        if (status.logs && status.logs.length) {
            log.textContent = status.logs.join('\n');
            log.scrollTop = log.scrollHeight;
        }

        if (status.status === 'running' || status.status === 'starting') {
            setTimeout(pollTrainingStatus, 2000);
        } else {
            btn.disabled = false;
            btn.textContent = 'Start Training';
            loadStats();
        }
    } catch (err) {
        btn.disabled = false;
        btn.textContent = 'Start Training';
    }
}

// ---------------------------------------------------------------------------
// Test tab
// ---------------------------------------------------------------------------

function handleTestFile(file) {
    if (!file) return;
    testFile = file;
    const dropzone = document.getElementById('test-dropzone');
    dropzone.innerHTML = `
        <img src="${URL.createObjectURL(file)}" style="max-height:200px;border-radius:var(--pico-border-radius);">
        <p class="upload-text">${file.name}</p>
    `;
}

function clearTestInput() {
    testFile = null;
    const dropzone = document.getElementById('test-dropzone');
    dropzone.innerHTML = `
        <input type="file" id="test-file-input" accept="image/*" style="display:none" onchange="handleTestFile(this.files[0])">
        <div class="upload-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        </div>
        <p class="upload-text">Drop an image to test</p>
    `;
    document.getElementById('test-results').innerHTML = `
        <h4>RESULTS</h4>
        <div class="empty-state"><p>No Results — Invoke the function to see results</p></div>
    `;
}

async function invokeTest() {
    if (!testFile) {
        showToast('Please select an image first', true);
        return;
    }

    const results = document.getElementById('test-results');
    results.innerHTML = '<h4>RESULTS</h4><p>Running inference...</p>';

    const fd = new FormData();
    fd.append('file', testFile);

    try {
        const data = await API.upload(`/api/v1/projects/${PROJECT_ID}/test/invoke`, fd);
        const resultColor = data.result === 'pass' ? '#4caf50' : '#f44336';
        results.innerHTML = `
            <h4>RESULTS</h4>
            <div class="test-result-card">
                <div style="display:flex;align-items:center;gap:1rem;">
                    <span class="badge badge-${data.result}" style="font-size:1rem;padding:0.3rem 0.8rem;">${data.result.toUpperCase()}</span>
                    <span style="font-size:1.2rem;font-weight:600;color:${resultColor};">${(data.confidence_score * 100).toFixed(1)}% confidence</span>
                </div>
                <p class="text-muted" style="margin-top:0.75rem;">Model: ${data.model_version} | Processing: ${data.processing_time_ms}ms</p>
            </div>
        `;
        loadStats();
    } catch (err) {
        results.innerHTML = `<h4>RESULTS</h4><div class="test-result-card"><p style="color:#f44336;">Error: ${err.message}</p></div>`;
    }
}

// ---------------------------------------------------------------------------
// Review tab
// ---------------------------------------------------------------------------

async function loadReviewImages() {
    const filter = document.getElementById('review-filter');
    const result = filter ? filter.value : '';
    const params = { limit: 100 };
    if (result) params.result = result;

    try {
        const data = await API.get(`/api/v1/projects/${PROJECT_ID}/inspections`, params);
        renderReviewGallery(data.inspections || []);
    } catch (err) {
        console.error('Failed to load review images:', err);
    }
}

function renderReviewGallery(inspections) {
    const gallery = document.getElementById('review-gallery');
    if (!inspections.length) {
        gallery.innerHTML = '<div class="empty-state"><p>No inspections yet. Run a test first.</p></div>';
        return;
    }
    gallery.innerHTML = inspections.map(insp => {
        const resultBadge = insp.result === 'pass'
            ? '<span class="badge badge-pass">PASS</span>'
            : insp.result === 'fail'
                ? '<span class="badge badge-fail">FAIL</span>'
                : '<span class="badge badge-pending">' + insp.status + '</span>';
        const confidence = insp.confidence_score != null ? (insp.confidence_score * 100).toFixed(1) + '%' : '--';
        const imageUrl = insp.image_id ? `/api/v1/images/${insp.image_id}/file` : '';
        return `
            <div class="gallery-item review-item">
                ${imageUrl ? `<img src="${imageUrl}" alt="Inspection image" loading="lazy">` : '<div class="review-no-image">No image</div>'}
                <div class="caption" style="padding:0.75rem;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                        ${resultBadge}
                        <span style="font-size:0.8rem;font-weight:600;">${confidence}</span>
                    </div>
                    <div class="caption-date">${formatDate(insp.created_at)}</div>
                    <div class="review-actions">
                        <button class="btn-review-approve ${insp.result === 'pass' ? 'active' : ''}" onclick="reviewInspection('${insp.id}', 'pass')">Approve</button>
                        <button class="btn-review-reject ${insp.result === 'fail' ? 'active' : ''}" onclick="reviewInspection('${insp.id}', 'fail')">Reject</button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

async function reviewInspection(inspectionId, result) {
    try {
        await API.patch(`/api/v1/projects/${PROJECT_ID}/inspections/${inspectionId}/review`, { result });
        showToast(result === 'pass' ? 'Inspection approved' : 'Inspection rejected');
        loadReviewImages();
        loadStats();
    } catch (err) {
        showToast('Failed to update inspection: ' + err.message, true);
    }
}

// ---------------------------------------------------------------------------
// Integrate tab
// ---------------------------------------------------------------------------

function toggleApiKeyVisibility() {
    const input = document.getElementById('api-key-display');
    input.type = input.type === 'password' ? 'text' : 'password';
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function copyProjectId() {
    const id = document.getElementById('project-id-text').textContent;
    navigator.clipboard.writeText(id).then(() => showToast('Project ID copied'));
}
