/**
 * Training Manager page — upload training images, start/monitor training.
 */
(function () {
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const categorySelect = document.getElementById('upload-category');
    const uploadProgress = document.getElementById('upload-progress');
    const uploadStatus = document.getElementById('upload-status');
    const uploadResults = document.getElementById('upload-results');
    const uploadResultsBody = document.getElementById('upload-results-body');
    const startBtn = document.getElementById('start-training-btn');
    const downloadBtn = document.getElementById('download-model-btn');
    const trainingProgress = document.getElementById('training-progress');
    const trainingFill = document.getElementById('training-fill');
    const trainingMessage = document.getElementById('training-message');
    const trainingStatusBadge = document.getElementById('training-status-badge');
    const trainingStatusText = document.getElementById('training-status-text');
    const trainingLogs = document.getElementById('training-logs');
    const goodBadge = document.getElementById('good-badge');
    const defectBadge = document.getElementById('defect-badge');

    let pollInterval = null;

    // Color-code the category dropdown on change
    function updateCategoryStyle() {
        categorySelect.classList.remove('cat-good', 'cat-defect');
        categorySelect.classList.add(
            categorySelect.value === 'good' ? 'cat-good' : 'cat-defect'
        );
    }
    categorySelect.addEventListener('change', updateCategoryStyle);

    // Load data stats
    async function loadStats() {
        try {
            const stats = await API.getTrainingStats();
            document.getElementById('good-count').textContent = stats.good_count;
            document.getElementById('defect-count').textContent = stats.defect_count;
            document.getElementById('total-training').textContent = stats.total;
            // Update count badges next to dropdown
            if (goodBadge) goodBadge.textContent = stats.good_count;
            if (defectBadge) defectBadge.textContent = stats.defect_count;
        } catch (e) {
            console.warn('Failed to load training stats:', e.message);
        }
    }

    // Upload zone — drag & drop
    uploadZone.addEventListener('click', () => fileInput.click());

    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', () => {
        handleFiles(fileInput.files);
        fileInput.value = '';
    });

    async function handleFiles(files) {
        if (!files.length) return;

        const category = categorySelect.value;
        uploadProgress.classList.remove('hidden');
        uploadResults.classList.remove('hidden');
        uploadResultsBody.innerHTML = '';

        let uploaded = 0;
        for (const file of files) {
            uploadStatus.textContent = `Uploading ${++uploaded} of ${files.length}...`;
            try {
                const result = await API.uploadTrainingImage(file, category);
                const row = document.createElement('tr');
                row.innerHTML = `<td>${result.filename}</td><td>${result.category}</td><td><span class="badge badge-pass">OK</span></td>`;
                uploadResultsBody.appendChild(row);
            } catch (e) {
                const row = document.createElement('tr');
                row.innerHTML = `<td>${file.name}</td><td>${category}</td><td><span class="badge badge-fail">${e.message}</span></td>`;
                uploadResultsBody.appendChild(row);
            }
        }

        uploadStatus.textContent = `Done — ${uploaded} file(s) processed`;
        loadStats();
    }

    // Start training
    startBtn.addEventListener('click', async () => {
        try {
            startBtn.disabled = true;
            await API.startTraining();
            showToast('Training started');
            startPolling();
        } catch (e) {
            showToast('Failed: ' + e.message, true);
            startBtn.disabled = false;
        }
    });

    // Download model
    downloadBtn.addEventListener('click', () => {
        window.location.href = '/api/v1/training/model';
    });

    // Poll training status
    function startPolling() {
        trainingProgress.classList.remove('hidden');
        trainingStatusBadge.classList.remove('hidden');

        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(pollStatus, 2000);
        pollStatus();
    }

    async function pollStatus() {
        try {
            const status = await API.getTrainingStatus();

            // Update progress bar
            trainingFill.style.width = status.progress + '%';
            trainingFill.textContent = status.progress + '%';

            // Update status badge
            trainingStatusText.innerHTML = `<span class="badge badge-${status.status === 'complete' ? 'pass' : status.status === 'failed' ? 'fail' : 'processing'}">${status.status}</span>`;

            // Update message
            if (status.message) {
                trainingMessage.textContent = status.message;
            }

            // Update logs
            if (status.logs && status.logs.length > 0) {
                trainingLogs.textContent = status.logs.join('\n');
                trainingLogs.scrollTop = trainingLogs.scrollHeight;
            }

            // Done?
            if (status.status === 'complete') {
                clearInterval(pollInterval);
                pollInterval = null;
                startBtn.disabled = false;
                downloadBtn.disabled = false;
                showToast('Training complete!');
            } else if (status.status === 'failed') {
                clearInterval(pollInterval);
                pollInterval = null;
                startBtn.disabled = false;
                showToast('Training failed: ' + status.message, true);
            }
        } catch (e) {
            console.warn('Poll error:', e.message);
        }
    }

    // Check if training is already running on page load
    async function checkInitialStatus() {
        try {
            const status = await API.getTrainingStatus();
            if (status.status === 'running' || status.status === 'starting') {
                startBtn.disabled = true;
                startPolling();
            } else if (status.status === 'complete' && status.model_path) {
                downloadBtn.disabled = false;
                trainingStatusBadge.classList.remove('hidden');
                trainingStatusText.innerHTML = '<span class="badge badge-pass">complete</span>';
                if (status.logs && status.logs.length > 0) {
                    trainingLogs.textContent = status.logs.join('\n');
                }
            }
        } catch (e) {
            // No previous training
        }
    }

    // Initialize
    updateCategoryStyle();
    loadStats();
    checkInitialStatus();
})();
