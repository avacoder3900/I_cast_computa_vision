/**
 * Inspection History page — filterable list with detail modal.
 */
(function () {
    const tbody = document.getElementById('inspections-body');
    const filterBtn = document.getElementById('filter-btn');
    const clearBtn = document.getElementById('clear-btn');
    const loadMoreBtn = document.getElementById('load-more-btn');
    const modal = document.getElementById('inspection-modal');
    const modalClose = document.getElementById('modal-close');
    const modalCloseBtn = document.getElementById('modal-close-btn');

    let currentSkip = 0;
    const PAGE_SIZE = 50;

    function getFilters() {
        return {
            cartridge_id: document.getElementById('filter-cartridge').value.trim() || undefined,
            phase: document.getElementById('filter-phase').value || undefined,
            result: document.getElementById('filter-result').value || undefined,
        };
    }

    async function loadInspections(append = false) {
        try {
            const filters = getFilters();
            const params = {
                ...filters,
                skip: currentSkip,
                limit: PAGE_SIZE,
            };

            const inspections = await API.listInspections(params);

            if (!append) {
                tbody.innerHTML = '';
            }

            if (inspections.length === 0 && !append) {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No inspections found</td></tr>';
                loadMoreBtn.classList.add('hidden');
                return;
            }

            inspections.forEach(insp => {
                const tr = document.createElement('tr');
                tr.dataset.result = insp.result || 'pending';
                tr.style.cursor = 'pointer';
                tr.addEventListener('click', () => showDetail(insp));

                const resultBadge = insp.result
                    ? `<span class="badge badge-${insp.result}">${insp.result}</span>`
                    : '—';

                const statusBadge = `<span class="badge badge-${insp.status}">${insp.status}</span>`;

                const score = insp.confidence_score !== null
                    ? (insp.confidence_score * 100).toFixed(1) + '%'
                    : '—';

                const defectCount = insp.defects ? insp.defects.length : 0;

                tr.innerHTML = `
                    <td><code>${insp.id.substring(0, 10)}</code></td>
                    <td>${insp.cartridge_record_id
                        ? `<a href="/ui/cartridge/${insp.cartridge_record_id}">${insp.cartridge_record_id.substring(0, 12)}</a>`
                        : '—'}</td>
                    <td>${insp.phase || '—'}</td>
                    <td>${statusBadge}</td>
                    <td>${resultBadge}</td>
                    <td>${score}</td>
                    <td>${defectCount > 0 ? defectCount : '—'}</td>
                    <td>${formatDate(insp.created_at)}</td>
                `;
                tbody.appendChild(tr);
            });

            loadMoreBtn.classList.toggle('hidden', inspections.length < PAGE_SIZE);
            currentSkip += inspections.length;

        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Error: ${e.message}</td></tr>`;
        }
    }

    async function showDetail(insp) {
        document.getElementById('modal-id').textContent = insp.id;
        document.getElementById('modal-sample').textContent = insp.sample_id;
        document.getElementById('modal-cartridge').textContent = insp.cartridge_record_id || '—';
        document.getElementById('modal-phase').textContent = insp.phase || '—';
        document.getElementById('modal-type').textContent = insp.inspection_type;
        document.getElementById('modal-status').innerHTML = `<span class="badge badge-${insp.status}">${insp.status}</span>`;

        if (insp.result) {
            document.getElementById('modal-result').innerHTML = `<span class="badge badge-${insp.result}">${insp.result}</span>`;
        } else {
            document.getElementById('modal-result').textContent = '—';
        }

        document.getElementById('modal-score').textContent =
            insp.confidence_score !== null ? (insp.confidence_score * 100).toFixed(1) + '%' : '—';
        document.getElementById('modal-model').textContent = insp.model_version || '—';
        document.getElementById('modal-time').textContent =
            insp.processing_time_ms ? insp.processing_time_ms + 'ms' : '—';
        document.getElementById('modal-created').textContent = formatDate(insp.created_at);
        document.getElementById('modal-completed').textContent = formatDate(insp.completed_at);

        // Defects
        const defectsEl = document.getElementById('modal-defects');
        if (insp.defects && insp.defects.length > 0) {
            let html = '<table><thead><tr><th>Type</th><th>Location</th><th>Severity</th></tr></thead><tbody>';
            insp.defects.forEach(d => {
                html += `<tr><td>${d.type}</td><td>${d.location}</td><td>${d.severity}</td></tr>`;
            });
            html += '</tbody></table>';
            defectsEl.innerHTML = html;
        } else {
            defectsEl.textContent = 'No defects found';
        }

        // Image
        const imgEl = document.getElementById('modal-image');
        imgEl.src = API.getImageUrl(insp.image_id);
        imgEl.alt = `Inspection ${insp.id}`;

        modal.showModal();
    }

    // Filter events
    filterBtn.addEventListener('click', () => {
        currentSkip = 0;
        loadInspections(false);
    });

    clearBtn.addEventListener('click', () => {
        document.getElementById('filter-cartridge').value = '';
        document.getElementById('filter-phase').value = '';
        document.getElementById('filter-result').value = '';
        currentSkip = 0;
        loadInspections(false);
    });

    loadMoreBtn.addEventListener('click', () => {
        loadInspections(true);
    });

    // Modal close
    modalClose.addEventListener('click', () => modal.close());
    modalCloseBtn.addEventListener('click', () => modal.close());
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.close();
    });

    // Check URL params for direct inspection view
    const urlParams = new URLSearchParams(window.location.search);
    const directId = urlParams.get('id');
    if (directId) {
        API.getInspection(directId).then(showDetail).catch(() => {});
    }

    // Initial load
    loadInspections();
})();
