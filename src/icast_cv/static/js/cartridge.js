/**
 * Cartridge detail view — shows all inspections & images for a cartridge,
 * organized by manufacturing phase.
 */
(function () {
    const container = document.getElementById('phases-container');

    async function loadCartridgeData() {
        try {
            // Fetch inspections for this cartridge
            const inspections = await API.listInspections({
                cartridge_id: CARTRIDGE_ID,
                limit: 200,
            });

            // Fetch images for this cartridge
            const images = await API.listImages({
                cartridge_id: CARTRIDGE_ID,
                limit: 200,
            });

            // Update stats
            const total = inspections.length;
            const passCount = inspections.filter(i => i.result === 'pass').length;
            const failCount = inspections.filter(i => i.result === 'fail').length;

            document.getElementById('cart-total').textContent = total;
            document.getElementById('cart-pass').textContent = passCount;
            document.getElementById('cart-fail').textContent = failCount;
            document.getElementById('cart-images').textContent = images.length;

            if (inspections.length === 0 && images.length === 0) {
                container.innerHTML = '<div class="empty-state"><p>No data found for this cartridge.</p></div>';
                return;
            }

            // Group by phase
            const phases = ['backing', 'wax_filled', 'reagent_filled', 'inspected', 'sealed'];
            const phaseMap = {};

            // Initialize all known phases
            phases.forEach(p => { phaseMap[p] = { inspections: [], images: [] }; });
            phaseMap['untagged'] = { inspections: [], images: [] };

            // Assign inspections
            inspections.forEach(insp => {
                const phase = insp.phase || 'untagged';
                if (!phaseMap[phase]) phaseMap[phase] = { inspections: [], images: [] };
                phaseMap[phase].inspections.push(insp);
            });

            // Assign images
            images.forEach(img => {
                const phase = (img.cartridge_tag && img.cartridge_tag.phase) || 'untagged';
                if (!phaseMap[phase]) phaseMap[phase] = { inspections: [], images: [] };
                phaseMap[phase].images.push(img);
            });

            // Render phases
            container.innerHTML = '';
            const allPhases = [...phases, 'untagged'];

            allPhases.forEach(phaseName => {
                const data = phaseMap[phaseName];
                if (!data || (data.inspections.length === 0 && data.images.length === 0)) return;

                const section = document.createElement('div');
                section.className = 'phase-section';

                const phaseLabel = phaseName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                let html = `<h4>${phaseLabel}</h4>`;

                // Image gallery
                if (data.images.length > 0) {
                    html += '<div class="gallery">';
                    data.images.forEach(img => {
                        html += `
                            <div class="gallery-item">
                                <img src="${API.getThumbUrl(img.id)}" alt="${img.filename}" loading="lazy">
                                <div class="caption">
                                    <small>${formatDate(img.captured_at)}</small>
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                }

                // Inspections table
                if (data.inspections.length > 0) {
                    html += `<table class="mt-1"><thead><tr>
                        <th>ID</th><th>Result</th><th>Score</th><th>Defects</th><th>Date</th>
                    </tr></thead><tbody>`;

                    data.inspections.forEach(insp => {
                        const resultBadge = insp.result
                            ? `<span class="badge badge-${insp.result}">${insp.result}</span>`
                            : `<span class="badge badge-pending">${insp.status}</span>`;

                        const score = insp.confidence_score !== null
                            ? (insp.confidence_score * 100).toFixed(1) + '%'
                            : '—';

                        html += `<tr data-result="${insp.result || 'pending'}">
                            <td><a href="/ui/inspections?id=${insp.id}"><code>${insp.id.substring(0, 10)}</code></a></td>
                            <td>${resultBadge}</td>
                            <td>${score}</td>
                            <td>${insp.defects ? insp.defects.length : 0}</td>
                            <td>${formatDate(insp.created_at)}</td>
                        </tr>`;
                    });

                    html += '</tbody></table>';
                }

                section.innerHTML = html;
                container.appendChild(section);
            });

        } catch (e) {
            container.innerHTML = `<div class="empty-state"><p>Error loading data: ${e.message}</p></div>`;
        }
    }

    loadCartridgeData();
})();
