/**
 * ICast CV API client — shared fetch helpers.
 * All UI pages import this for consistent API access.
 */
const API = {
    /** Base URL for API calls (same origin) */
    baseUrl: '',

    /** API key header (empty = auth disabled) */
    apiKey: '',

    /** Set API key for authenticated requests */
    setApiKey(key) {
        this.apiKey = key;
        localStorage.setItem('icast_api_key', key);
    },

    /** Load saved API key from localStorage */
    init() {
        this.apiKey = localStorage.getItem('icast_api_key') || '';
    },

    /** Build headers object */
    _headers(extra = {}) {
        const h = { ...extra };
        if (this.apiKey) {
            h['X-API-Key'] = this.apiKey;
        }
        return h;
    },

    /** Generic fetch wrapper with error handling */
    async request(method, path, { body, params, isFormData } = {}) {
        let url = `${this.baseUrl}${path}`;
        if (params) {
            const qs = new URLSearchParams();
            for (const [k, v] of Object.entries(params)) {
                if (v !== null && v !== undefined && v !== '') {
                    qs.append(k, v);
                }
            }
            const qstr = qs.toString();
            if (qstr) url += '?' + qstr;
        }

        const opts = { method, headers: this._headers() };

        if (body && isFormData) {
            opts.body = body;
        } else if (body) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        }

        const resp = await fetch(url, opts);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        if (resp.status === 204) return null;
        return resp.json();
    },

    // Convenience methods
    get(path, params) { return this.request('GET', path, { params }); },
    post(path, body) { return this.request('POST', path, { body }); },
    patch(path, body) { return this.request('PATCH', path, { body }); },
    del(path) { return this.request('DELETE', path); },
    upload(path, formData) { return this.request('POST', path, { body: formData, isFormData: true }); },

    // --- Domain-specific API methods ---

    // Dashboard
    getStats() { return this.get('/api/v1/dashboard/stats'); },

    // Samples
    listSamples(params) { return this.get('/api/v1/samples', params); },
    getSample(id) { return this.get(`/api/v1/samples/${id}`); },
    createSample(data) { return this.post('/api/v1/samples', data); },

    // Images
    listImages(params) { return this.get('/api/v1/images', params); },
    getImageUrl(id) { return `/api/v1/images/${id}/file`; },
    getThumbUrl(id) { return `/api/v1/images/${id}/thumbnail`; },

    // Cameras
    listCameras() { return this.get('/api/v1/cameras'); },

    // Capture
    captureImage(data) { return this.post('/api/v1/capture', data); },
    captureAndInspect(sampleId, data) {
        return this.post(`/api/v1/samples/${sampleId}/capture-and-inspect`, data);
    },

    // Inspections
    listInspections(params) { return this.get('/api/inspections', params); },
    getInspection(id) { return this.get(`/api/inspections/${id}`); },
    pollInspection(id) { return this.get(`/api/inspections/${id}/poll`); },

    // Training
    getTrainingStats() { return this.get('/api/v1/training/data-stats'); },
    getTrainingStatus() { return this.get('/api/v1/training/status'); },
    startTraining() { return this.post('/api/v1/training/start'); },
    uploadTrainingImage(file, category) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('category', category);
        return this.upload('/api/v1/training/upload', fd);
    },
    listTrainingImages(params) { return this.get('/api/v1/training/images', params); },
    recategorizeImage(filename, newCategory) {
        return this.patch(`/api/v1/training/images/${filename}`, { new_category: newCategory });
    },
    batchRecategorize(filenames, newCategory) {
        return this.patch('/api/v1/training/images-batch', { filenames, new_category: newCategory });
    },

    // Gallery
    getGalleryAll(params) { return this.get('/api/v1/gallery/all', params); },

    // Projects
    listProjects(params) { return this.get('/api/v1/projects', params); },
    getProject(id) { return this.get(`/api/v1/projects/${id}`); },
    createProject(data) { return this.post('/api/v1/projects', data); },
    updateProject(id, data) { return this.patch(`/api/v1/projects/${id}`, data); },
    deleteProject(id) { return this.del(`/api/v1/projects/${id}`); },
    duplicateProject(id) { return this.post(`/api/v1/projects/${id}/duplicate`); },
    getProjectStats(id) { return this.get(`/api/v1/projects/${id}/stats`); },
    getProjectImages(id, params) { return this.get(`/api/v1/projects/${id}/images`, params); },
    labelProjectImage(projectId, imageId, label) {
        return this.patch(`/api/v1/projects/${projectId}/images/${imageId}/label`, { label });
    },
    getProjectTrainingStats(id) { return this.get(`/api/v1/projects/${id}/training/data-stats`); },
    getProjectTrainingImages(id, params) { return this.get(`/api/v1/projects/${id}/training/images`, params); },
    uploadProjectTrainingImage(id, file, category) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('category', category);
        return this.upload(`/api/v1/projects/${id}/training/upload`, fd);
    },
    getProjectInspections(id, params) { return this.get(`/api/v1/projects/${id}/inspections`, params); },
    getGlobalLabels() { return this.get('/api/v1/projects/labels/global'); },
};

// Auto-init
API.init();

/** Format an ISO date string for display */
function formatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/** Create a status/result badge element */
function badge(value, type) {
    const span = document.createElement('span');
    span.className = `badge badge-${type || value}`;
    span.textContent = value;
    return span;
}

/** Show a toast notification */
function showToast(message, isError = false) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 1000;
        padding: 0.75rem 1.25rem; border-radius: 0.5rem; font-size: 0.9rem;
        background: ${isError ? '#b71c1c' : '#1b5e20'}; color: white;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3); transition: opacity 0.3s;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; }, 2500);
    setTimeout(() => { toast.remove(); }, 3000);
}
