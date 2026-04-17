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
    REGION: 'us-east-1'
};
