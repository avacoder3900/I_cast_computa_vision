/**
 * Capture & Inspect page — camera selection, photo capture, inspection polling.
 */
(function () {
    const sampleInput = document.getElementById('sample-id');
    const cameraSelect = document.getElementById('camera-select');
    const phaseSelect = document.getElementById('phase-select');
    const tagsInput = document.getElementById('tags-input');
    const captureBtn = document.getElementById('capture-btn');
    const captureStatus = document.getElementById('capture-status');
    const resultSection = document.getElementById('result-section');
    const samplesList = document.getElementById('samples-list');

    // Load cameras
    async function loadCameras() {
        try {
            const cameras = await API.listCameras();
            cameraSelect.innerHTML = '';
            if (cameras.length === 0) {
                cameraSelect.innerHTML = '<option value="0">Camera 0 (default)</option>';
                return;
            }
            cameras.forEach(cam => {
                const opt = document.createElement('option');
                opt.value = cam.index;
                opt.textContent = `Camera ${cam.index}${cam.name ? ' — ' + cam.name : ''}${cam.is_open ? '' : ' (offline)'}`;
                cameraSelect.appendChild(opt);
            });
        } catch (e) {
            cameraSelect.innerHTML = '<option value="0">Camera 0 (default)</option>';
        }
    }

    // Load existing samples for quick selection
    async function loadSamples() {
        try {
            const samples = await API.listSamples({ limit: 20 });
            if (samples.length === 0) {
                samplesList.innerHTML = '<p class="text-muted">No samples found. Enter an ID above or create a sample via the API.</p>';
                return;
            }
            let html = '<table><thead><tr><th>ID</th><th>Name</th><th>Project</th><th>Action</th></tr></thead><tbody>';
            samples.forEach(s => {
                html += `<tr>
                    <td><code>${s.id.substring(0, 12)}</code></td>
                    <td>${s.name}</td>
                    <td>${s.project || '—'}</td>
                    <td><button class="outline secondary select-sample-btn" data-id="${s.id}">Select</button></td>
                </tr>`;
            });
            html += '</tbody></table>';
            samplesList.innerHTML = html;

            // Bind select buttons
            samplesList.querySelectorAll('.select-sample-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    sampleInput.value = btn.dataset.id;
                    showToast('Sample selected');
                });
            });
        } catch (e) {
            samplesList.innerHTML = '<p class="text-muted">Could not load samples.</p>';
        }
    }

    // Capture and inspect
    captureBtn.addEventListener('click', async () => {
        const sampleId = sampleInput.value.trim();
        if (!sampleId) {
            showToast('Please enter a sample/cartridge ID', true);
            return;
        }

        captureBtn.disabled = true;
        captureStatus.classList.remove('hidden');
        resultSection.classList.add('hidden');

        try {
            const data = {
                camera_index: parseInt(cameraSelect.value, 10),
                inspection_type: 'anomaly_detection',
                metadata: {},
            };

            // Add tags if provided
            const tags = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean);
            if (tags.length > 0) {
                data.metadata.tags = tags;
            }

            const resp = await API.captureAndInspect(sampleId, data);

            // Show image
            document.getElementById('result-image').src = API.getImageUrl(resp.image.id);
            document.getElementById('result-id').textContent = resp.inspection.id;

            // Poll for result
            resultSection.classList.remove('hidden');
            captureStatus.classList.add('hidden');
            await pollForResult(resp.inspection.id);

        } catch (e) {
            showToast('Capture failed: ' + e.message, true);
            captureStatus.classList.add('hidden');
        } finally {
            captureBtn.disabled = false;
        }
    });

    // Poll inspection until complete
    async function pollForResult(inspectionId) {
        const statusEl = document.getElementById('result-status');
        const resultEl = document.getElementById('result-result');
        const scoreEl = document.getElementById('result-score');
        const defectsEl = document.getElementById('result-defects');
        const timeEl = document.getElementById('result-time');

        statusEl.innerHTML = '<span class="badge badge-pending">pending</span>';
        resultEl.textContent = '—';
        scoreEl.textContent = '—';
        defectsEl.textContent = '—';
        timeEl.textContent = '—';

        for (let i = 0; i < 60; i++) {
            await new Promise(r => setTimeout(r, 2000));
            try {
                const insp = await API.pollInspection(inspectionId);

                if (insp.status === 'complete' || insp.status === 'failed') {
                    statusEl.innerHTML = `<span class="badge badge-${insp.status}">${insp.status}</span>`;

                    if (insp.result) {
                        resultEl.innerHTML = `<span class="badge badge-${insp.result}">${insp.result}</span>`;
                    }
                    if (insp.confidence_score !== null) {
                        scoreEl.textContent = (insp.confidence_score * 100).toFixed(1) + '%';
                    }
                    if (insp.defects && insp.defects.length > 0) {
                        defectsEl.textContent = insp.defects.map(d => `${d.type} (${d.severity})`).join(', ');
                    } else {
                        defectsEl.textContent = 'None';
                    }
                    if (insp.processing_time_ms) {
                        timeEl.textContent = insp.processing_time_ms + 'ms';
                    }

                    showToast(`Inspection ${insp.result || insp.status}!`);
                    return;
                }

                statusEl.innerHTML = `<span class="badge badge-processing">${insp.status}</span>`;
            } catch (e) {
                console.warn('Poll error:', e.message);
            }
        }

        statusEl.textContent = 'Timed out waiting for result';
    }

    // Initialize
    loadCameras();
    loadSamples();
})();
