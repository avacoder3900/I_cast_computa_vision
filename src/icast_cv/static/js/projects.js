/**
 * Projects landing page — list, create, search, sort projects.
 */

const BIMS_PHASES = [
    'backing', 'wax_filled', 'wax_qc', 'wax_stored', 'reagent_filled',
    'inspected', 'sealed', 'cured', 'stored', 'released', 'shipped',
    'assay_loaded', 'testing', 'completed', 'voided',
];

const TYPE_LABELS = {
    classification: 'CLASSIFYING IMAGES',
    anomaly_detection: 'ANOMALY DETECTION',
    object_detection: 'OBJECT DETECTION',
};

const BORDER_COLORS = ['#6366f1', '#d4a017', '#4caf50', '#f44336', '#00bcd4', '#ff9800', '#9c27b0', '#e91e63'];

let currentPage = 0;
const PAGE_SIZE = 10;
let totalProjects = 0;
let contextMenuProjectId = null;
let searchTimeout = null;

// Init
document.addEventListener('DOMContentLoaded', () => {
    populatePhases();
    loadProjects();
    document.addEventListener('click', () => {
        document.getElementById('context-menu').style.display = 'none';
    });
});

function populatePhases() {
    const container = document.getElementById('phases-checkboxes');
    container.innerHTML = BIMS_PHASES.map(p =>
        `<label><input type="checkbox" value="${p}"> ${p.replace(/_/g, ' ')}</label>`
    ).join('');
}

function debounceSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        currentPage = 0;
        loadProjects();
    }, 300);
}

async function loadProjects() {
    const search = document.getElementById('project-search').value.trim();
    const sortVal = document.getElementById('sort-select').value;

    let sortBy = 'created_at';
    let sortOrder = -1;
    if (sortVal === 'oldest') { sortBy = 'created_at'; sortOrder = 1; }
    if (sortVal === 'name') { sortBy = 'name'; sortOrder = 1; }

    const params = {
        skip: currentPage * PAGE_SIZE,
        limit: PAGE_SIZE,
        sort_by: sortBy,
        sort_order: sortOrder,
    };
    if (search) params.search = search;

    try {
        const data = await API.get('/api/v1/projects', params);
        totalProjects = data.total;
        renderProjects(data.projects);
        renderPagination();
    } catch (err) {
        console.error('Failed to load projects:', err);
    }
}

function renderProjects(projects) {
    const grid = document.getElementById('projects-grid');
    const empty = document.getElementById('projects-empty');

    if (projects.length === 0) {
        grid.innerHTML = '';
        grid.appendChild(empty);
        empty.style.display = '';
        return;
    }

    grid.innerHTML = projects.map((p, i) => {
        const color = BORDER_COLORS[i % BORDER_COLORS.length];
        const typeLabel = TYPE_LABELS[p.project_type] || p.project_type.toUpperCase();
        return `
        <div class="project-card" onclick="goToProject('${p.id}')">
            <div class="project-card-border" style="background:${color}"></div>
            <div class="project-card-info">
                <div class="project-card-name">${escHtml(p.name)}</div>
                <div class="project-card-type">${typeLabel}</div>
                <div class="project-card-id">
                    <code>${p.id}</code>
                    <span class="copy-icon" onclick="event.stopPropagation(); copyId('${p.id}')" title="Copy ID">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                    </span>
                </div>
            </div>
            <div class="project-card-stats">
                <div class="project-card-annotation">${p.annotated_count}/${p.image_count}</div>
                <div class="project-card-annotation-label">SAMPLES ANNOTATED</div>
            </div>
            <button class="project-card-menu" onclick="event.stopPropagation(); showContextMenu(event, '${p.id}')">&#8942;</button>
        </div>`;
    }).join('');
}

function renderPagination() {
    const pag = document.getElementById('projects-pagination');
    const info = document.getElementById('pagination-info');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');

    if (totalProjects === 0) {
        pag.style.display = 'none';
        return;
    }

    pag.style.display = 'flex';
    const start = currentPage * PAGE_SIZE + 1;
    const end = Math.min(start + PAGE_SIZE - 1, totalProjects);
    info.textContent = `${start}-${end} of ${totalProjects}`;
    prevBtn.disabled = currentPage === 0;
    nextBtn.disabled = end >= totalProjects;
}

function prevPage() { currentPage--; loadProjects(); }
function nextPage() { currentPage++; loadProjects(); }

function goToProject(id) {
    window.location.href = `/ui/project/${id}`;
}

function copyId(id) {
    navigator.clipboard.writeText(id).then(() => showToast('Project ID copied'));
}

// Context menu
function showContextMenu(event, projectId) {
    event.preventDefault();
    contextMenuProjectId = projectId;
    const menu = document.getElementById('context-menu');
    menu.style.display = 'block';
    menu.style.left = event.clientX + 'px';
    menu.style.top = event.clientY + 'px';
}

async function editProject() {
    if (!contextMenuProjectId) return;
    goToProject(contextMenuProjectId);
}

async function duplicateProject() {
    if (!contextMenuProjectId) return;
    try {
        await API.post(`/api/v1/projects/${contextMenuProjectId}/duplicate`);
        showToast('Project duplicated');
        loadProjects();
    } catch (err) {
        showToast('Failed to duplicate: ' + err.message, true);
    }
}

async function deleteProject() {
    if (!contextMenuProjectId) return;
    if (!confirm('Delete this project? This cannot be undone.')) return;
    try {
        await API.del(`/api/v1/projects/${contextMenuProjectId}`);
        showToast('Project deleted');
        loadProjects();
    } catch (err) {
        showToast('Failed to delete: ' + err.message, true);
    }
}

// New project modal
function openNewProjectModal() {
    document.getElementById('new-project-modal').style.display = 'flex';
    document.getElementById('project-name').focus();
}

function closeNewProjectModal() {
    document.getElementById('new-project-modal').style.display = 'none';
    document.getElementById('new-project-form').reset();
}

function closeModalOnOverlay(event) {
    if (event.target === event.currentTarget) closeNewProjectModal();
}

async function createProject(event) {
    event.preventDefault();

    const name = document.getElementById('project-name').value.trim();
    const description = document.getElementById('project-description').value.trim();
    const projectType = document.getElementById('project-type').value;
    const tagsStr = document.getElementById('project-tags').value.trim();
    const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];

    const phaseCheckboxes = document.querySelectorAll('#phases-checkboxes input:checked');
    const phases = Array.from(phaseCheckboxes).map(cb => cb.value);

    try {
        const project = await API.post('/api/v1/projects', {
            name,
            description,
            project_type: projectType,
            tags,
            phases,
        });
        closeNewProjectModal();
        window.location.href = `/ui/project/${project.id}`;
    } catch (err) {
        showToast('Failed to create project: ' + err.message, true);
    }
}

function escHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
