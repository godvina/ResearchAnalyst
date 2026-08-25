/**
 * UAP Command Center — narratives (intentionally minimal).
 *
 * The rebuilt UAP Command Center computes its intelligence readouts LIVE and
 * fully grounded from window.UAP_DATA (signature counts, country breadth, UTS
 * coverage, ICD-203 confidence). It does not depend on pre-generated LLM prose,
 * which is what previously introduced embellishment (fabricated cases/names).
 *
 * These structures are left empty so the page loads without error. If AI prose
 * is added later it MUST pass the grounding validator in
 * scripts/generate_uap_command_center_narratives.py (temp 0 + source-vocabulary
 * check) before being written here.
 */
window.UAP_BRIEFS = {};
window.UAP_MISSIONS = {};
window.UAP_CHAPTERS = {};
window.UAP_CONNECTIONS = {};
