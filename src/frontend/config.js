/**
 * Shared configuration for all Research Analyst Platform frontend pages.
 * Deployment tooling replaces placeholder values during package generation.
 *
 * Usage in HTML pages:
 *   <script src="config.js"></script>
 *   <script>
 *     const API_URL = window.APP_CONFIG.API_URL;
 *   </script>
 */
window.APP_CONFIG = {
    API_URL: 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1',
    TENANT_NAME: 'Research Analyst Platform',
    MODULES_ENABLED: ['investigator', 'prosecutor', 'network_discovery', 'document_assembly'],
    REGION: 'us-east-1',

    // DEMO_TIER controls which demos are visible in the UI (see docs/domain-pack-standard.md).
    //   'serious' = show only serious/client use cases; hide reference (UAP, Ancient Mysteries) + internal demos. Default for customer/serious audiences.
    //   'all'     = show everything, including the reference "prove-the-approach" demos. Use for colleague explorations.
    // Any nav link or card tagged data-demo-tier="reference" or "internal" is hidden unless DEMO_TIER === 'all'.
    DEMO_TIER: 'all'
};

// Applies DEMO_TIER: hides elements tagged with a data-demo-tier the current tier shouldn't show.
// Reusable across every page — include applyDemoTier() after DOM load (config.js is loaded first).
window.applyDemoTier = function () {
    try {
        var tier = (window.APP_CONFIG && window.APP_CONFIG.DEMO_TIER) || 'all';
        if (tier === 'all') return; // show everything
        // In any non-'all' tier, hide reference + internal demos.
        var hideTiers = ['reference', 'internal'];
        document.querySelectorAll('[data-demo-tier]').forEach(function (el) {
            if (hideTiers.indexOf(el.getAttribute('data-demo-tier')) !== -1) {
                el.style.display = 'none';
            }
        });
    } catch (e) { /* non-fatal: leave UI as-is */ }
};
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', window.applyDemoTier);
    else window.applyDemoTier();
}
