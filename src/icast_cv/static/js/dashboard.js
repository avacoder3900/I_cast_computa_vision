/**
 * Dashboard page — auto-refreshes stats every 30 seconds.
 */
(function () {
    async function refreshStats() {
        try {
            // Use the server-rendered stats initially; refresh via API
            // The dashboard stats come from the inspection_crud.get_inspection_stats
            // which is called server-side. For client-side refresh, we fetch inspections.
            const inspections = await API.get('/api/inspections', { limit: 200 });

            let pass_count = 0, fail_count = 0, pending_count = 0;
            for (const i of inspections) {
                if (i.result === 'pass') pass_count++;
                else if (i.result === 'fail') fail_count++;
                if (i.status === 'pending' || i.status === 'processing') pending_count++;
            }
            const total = inspections.length;

            document.getElementById('total-inspections').textContent = total;
            document.getElementById('pass-count').textContent = pass_count;
            document.getElementById('fail-count').textContent = fail_count;
            document.getElementById('pending-count').textContent = pending_count;
            document.getElementById('pass-rate').textContent =
                total > 0 ? (pass_count / total * 100).toFixed(1) + '%' : '0%';
        } catch (e) {
            // Stats will remain at server-rendered values
            console.warn('Failed to refresh stats:', e.message);
        }
    }

    // Refresh every 30 seconds
    setInterval(refreshStats, 30000);
})();
