/**
 * Photo Gallery page — browse, re-tag, and re-categorize all images.
 */
(function () {
    const grid = document.getElementById('gallery-grid');
    const filterSource = document.getElementById('filter-source');
    const filterCategory = document.getElementById('filter-category');
    const filterBtn = document.getElementById('filter-btn');
    const selectAllCb = document.getElementById('select-all-cb');
    const selectedCount = document.getElementById('selected-count');
    const batchCategory = document.getElementById('batch-category');
    const batchBtn = document.getElementById('batch-recategorize-btn');

    // Lightbox elements
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxFilename = document.getElementById('lightbox-filename');
    const lightboxMeta = document.getElementById('lightbox-meta');
    const lightboxCategory = document.getElementById('lightbox-category');
    const lightboxTags = document.getElementById('lightbox-tags');
    const lightboxSave = document.getElementById('lightbox-save');
    const lightboxClose = document.getElementById('lightbox-close');

    const TAG_PRESETS = [
        'wax_fill', 'reagent_fill', 'top_seal', 'final_qc',
        'defect_crack', 'defect_bubble'
    ];

    let allImages = [];
    let selectedFiles = new Set();
    let currentLightboxImage = null;

    async function loadGallery() {
        grid.innerHTML = '<div class="empty-state"><p>Loading images...</p></div>';

        try {
            const source = filterSource.value || undefined;
            const params = {};
            if (source) params.source = source;
            params.limit = 200;

            const data = await API.get('/api/v1/gallery/all', params);
            allImages = data.images;

            // Apply client-side category filter
            let filtered = allImages;
            const catFilter = filterCategory.value;
            if (catFilter) {
                filtered = allImages.filter(img => img.category === catFilter);
            }

            renderGrid(filtered);
            updateCounts();
        } catch (e) {
            grid.innerHTML = `<div class="empty-state"><p>Failed to load: ${e.message}</p></div>`;
        }
    }

    function renderGrid(images) {
        if (!images.length) {
            grid.innerHTML = '<div class="empty-state"><p>No images found</p></div>';
            return;
        }

        grid.innerHTML = '';
        images.forEach(img => {
            const item = document.createElement('div');
            item.className = 'gallery-item';
            item.dataset.filename = img.filename;
            item.dataset.source = img.source;
            item.dataset.category = img.category;

            const isTraining = img.source === 'training';
            const categoryClass = img.category === 'good' ? 'badge-pass'
                : img.category === 'defect' ? 'badge-fail'
                : img.category === 'uncategorized' ? 'badge-pending'
                : 'badge-processing';

            const tagsStr = (img.tags || []).join(', ');
            const dateStr = img.uploaded_at ? formatDate(img.uploaded_at) : '';

            item.innerHTML = `
                <div class="gallery-checkbox">
                    <input type="checkbox" class="img-checkbox" data-filename="${img.filename}" ${isTraining ? '' : 'disabled'}>
                </div>
                <img src="${img.thumbnail_url}" alt="${img.filename}" loading="lazy"
                     onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22200%22><rect fill=%22%23333%22 width=%22200%22 height=%22200%22/><text fill=%22%23888%22 x=%2250%%22 y=%2250%%22 text-anchor=%22middle%22 dy=%22.3em%22>No preview</text></svg>'">
                <div class="caption">
                    <div class="caption-top">
                        <span class="badge ${categoryClass}">${img.category}</span>
                        <span class="badge badge-${img.source === 'training' ? 'complete' : 'processing'}">${img.source}</span>
                    </div>
                    <div class="caption-filename" title="${img.filename}">${img.filename}</div>
                    ${tagsStr ? `<div class="caption-tags">${tagsStr}</div>` : ''}
                    <div class="caption-date">${dateStr}</div>
                    ${isTraining ? `
                    <div class="caption-actions">
                        <select class="inline-category" data-filename="${img.filename}">
                            <option value="good" ${img.category === 'good' ? 'selected' : ''}>Good</option>
                            <option value="defect" ${img.category === 'defect' ? 'selected' : ''}>Defect</option>
                            <option value="uncategorized" ${img.category === 'uncategorized' ? 'selected' : ''}>Uncategorized</option>
                        </select>
                        <button class="save-single-btn outline secondary" data-filename="${img.filename}">Save</button>
                    </div>` : ''}
                </div>
            `;

            // Click image for lightbox
            item.querySelector('img').addEventListener('click', () => openLightbox(img));

            item.querySelector('.img-checkbox')?.addEventListener('change', updateSelection);

            // Inline save button
            const saveBtn = item.querySelector('.save-single-btn');
            if (saveBtn) {
                saveBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const select = item.querySelector('.inline-category');
                    const newCat = select.value;
                    try {
                        await API.patch(`/api/v1/training/images/${img.filename}`, { new_category: newCat });
                        showToast(`Moved "${img.filename}" to ${newCat}`);
                        loadGallery();
                    } catch (err) {
                        showToast('Error: ' + err.message, true);
                    }
                });
            }

            grid.appendChild(item);
        });
    }

    function updateCounts() {
        let good = 0, defect = 0, uncat = 0, inspection = 0;
        allImages.forEach(img => {
            if (img.category === 'good') good++;
            else if (img.category === 'defect') defect++;
            else if (img.category === 'uncategorized') uncat++;
            else if (img.source === 'inspection') inspection++;
        });
        document.getElementById('good-count').textContent = good;
        document.getElementById('defect-count').textContent = defect;
        document.getElementById('uncategorized-count').textContent = uncat;
        document.getElementById('inspection-count').textContent = inspection;
    }

    function updateSelection() {
        selectedFiles.clear();
        document.querySelectorAll('.img-checkbox:checked').forEach(cb => {
            selectedFiles.add(cb.dataset.filename);
        });
        selectedCount.textContent = selectedFiles.size + ' selected';
        batchBtn.disabled = selectedFiles.size === 0;
    }

    // Select all
    selectAllCb.addEventListener('change', () => {
        const checked = selectAllCb.checked;
        document.querySelectorAll('.img-checkbox:not(:disabled)').forEach(cb => {
            cb.checked = checked;
        });
        updateSelection();
    });

    // Filter
    filterBtn.addEventListener('click', loadGallery);

    // Batch re-categorize
    batchBtn.addEventListener('click', async () => {
        if (selectedFiles.size === 0) return;
        const newCat = batchCategory.value;
        batchBtn.disabled = true;
        try {
            await API.patch('/api/v1/training/images-batch', {
                filenames: Array.from(selectedFiles),
                new_category: newCat,
            });
            showToast(`Moved ${selectedFiles.size} image(s) to ${newCat}`);
            selectedFiles.clear();
            selectAllCb.checked = false;
            loadGallery();
        } catch (e) {
            showToast('Batch error: ' + e.message, true);
        } finally {
            batchBtn.disabled = false;
        }
    });

    // Lightbox
    function openLightbox(img) {
        currentLightboxImage = img;
        lightboxImg.src = img.file_url;
        lightboxFilename.textContent = img.filename;
        lightboxMeta.textContent = `Source: ${img.source} | Category: ${img.category} | ${img.uploaded_at ? formatDate(img.uploaded_at) : ''}`;
        lightboxCategory.value = img.category === 'inspection' ? 'good' : img.category;
        lightboxTags.value = (img.tags || []).join(', ');

        // Hide save controls for inspection images (can't move filesystem)
        const controls = lightbox.querySelector('.lightbox-controls');
        controls.style.display = img.source === 'training' ? '' : 'none';

        lightbox.style.display = 'flex';
    }

    lightboxClose.addEventListener('click', () => {
        lightbox.style.display = 'none';
        currentLightboxImage = null;
    });

    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) {
            lightbox.style.display = 'none';
            currentLightboxImage = null;
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && lightbox.style.display === 'flex') {
            lightbox.style.display = 'none';
            currentLightboxImage = null;
        }
    });

    lightboxSave.addEventListener('click', async () => {
        if (!currentLightboxImage || currentLightboxImage.source !== 'training') return;

        const newCat = lightboxCategory.value;
        try {
            await API.patch(`/api/v1/training/images/${currentLightboxImage.filename}`, {
                new_category: newCat,
            });
            showToast(`Updated "${currentLightboxImage.filename}"`);
            lightbox.style.display = 'none';
            loadGallery();
        } catch (e) {
            showToast('Error: ' + e.message, true);
        }
    });

    // Initialize
    loadGallery();
})();
