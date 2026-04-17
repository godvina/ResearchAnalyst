"""Pattern Discovery page.

Trigger pattern discovery, display pattern reports with ranked patterns,
and drill-down button to create sub-case files.

Requirements: 3.1, 3.3, 4.1
"""

import streamlit as st

import api_client
from validation import validate_topic_name, validate_description


def render():
    st.markdown("## 🔬 Pattern Discovery")

    # ── Case selector dropdown ───────────────────────────────────────
    try:
        data = api_client.list_case_files()
        cases = data.get("case_files", [])
    except Exception:
        cases = []

    if not cases:
        st.info("No case files found. Create one from the Case Dashboard.")
        return

    case_options = {f"{c['topic_name']} ({c['status']})": c['case_id'] for c in cases}
    selected_label = st.selectbox("Select Case", list(case_options.keys()))
    case_id = case_options[selected_label]

    st.caption(f"Case ID: `{case_id}`")

    # ── Trigger discovery ────────────────────────────────────────────
    if st.button("Run Pattern Discovery", type="primary"):
        with st.spinner("Discovering patterns... (this may take 10-20 seconds)"):
            try:
                report = api_client.discover_patterns(case_id)
                st.success("Pattern discovery complete.")
                _display_report(report, case_id)
            except api_client.APIError as exc:
                st.error(f"Discovery failed: {exc.detail}")
            except Exception as exc:
                st.error(f"Discovery failed: {exc}")

    # ── Show existing reports ────────────────────────────────────────
    st.markdown("### Existing Pattern Reports")
    try:
        data = api_client.get_patterns(case_id)
        reports = data.get("reports", [])
        if not reports:
            st.info("No pattern reports yet. Run discovery above.")
        for report in reports:
            _display_report(report, case_id)
    except api_client.APIError as exc:
        st.error(f"Could not load reports: {exc.detail}")
    except Exception as exc:
        st.error(f"Could not load reports: {exc}")


def _display_report(report: dict, case_id: str):
    """Render a single pattern report with ranked patterns."""
    rid = report.get("report_id", "?")
    with st.expander(f"Report {rid}", expanded=True):
        col1, col2, col3 = st.columns(3)
        col1.metric("Graph Patterns", report.get("graph_patterns_count", 0))
        col2.metric("Vector Patterns", report.get("vector_patterns_count", 0))
        col3.metric("Combined", report.get("combined_count", 0))

        patterns = report.get("patterns", [])
        for idx, p in enumerate(patterns):
            st.markdown(f"---\n**Pattern {idx + 1}** — "
                        f"Confidence: {p.get('confidence_score', 0):.2f} · "
                        f"Novelty: {p.get('novelty_score', 0):.2f}")
            st.write(p.get("explanation", ""))

            entities = p.get("entities_involved", [])
            if entities:
                st.markdown("Entities: " + ", ".join(
                    e.get("name", str(e)) for e in entities
                ))

            # Drill-down button
            btn_key = f"drill_{rid}_{idx}"
            if st.button("Drill Down →", key=btn_key):
                _show_drill_down_form(case_id, p)


def _show_drill_down_form(case_id: str, pattern: dict):
    """Show a form to create a sub-case file from a pattern."""
    st.markdown("#### Create Sub-Case File")
    with st.form(f"drill_form_{pattern.get('pattern_id', '')}"):
        topic = st.text_input("Sub-Case Topic", max_chars=255)
        desc = st.text_area("Description", max_chars=5000)
        submitted = st.form_submit_button("Create Sub-Case")

    if submitted:
        v_topic = validate_topic_name(topic)
        v_desc = validate_description(desc)
        if not v_topic.valid:
            st.error(v_topic.error)
        elif not v_desc.valid:
            st.error(v_desc.error)
        else:
            entity_names = [
                e.get("name", "") for e in pattern.get("entities_involved", [])
                if e.get("name")
            ]
            try:
                result = api_client.drill_down(
                    case_id,
                    topic.strip(),
                    desc.strip(),
                    entity_names=entity_names or None,
                    pattern_id=pattern.get("pattern_id"),
                )
                st.success(f"Sub-case created: {result.get('case_id', '')}")
            except api_client.APIError as exc:
                st.error(f"Drill-down failed: {exc.detail}")
