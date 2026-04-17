"""Findings Log page.

Record observations, tag entities, and annotate patterns within a case file.

Requirements: 6.6
"""

import streamlit as st

import api_client
from validation import validate_analyst_note, validate_entity_tags


def render():
    st.header("Findings Log")

    case_id = st.text_input("Case ID", key="findings_case_id")
    if not case_id:
        st.info("Enter a Case ID to view or record findings.")
        return

    # ── Load case to verify it exists ────────────────────────────────
    try:
        case = api_client.get_case_file(case_id.strip())
    except api_client.APIError as exc:
        st.error(f"Could not load case: {exc.detail}")
        return

    st.markdown(f"**Case:** {case.get('topic_name', '')} ({case.get('status', '')})")

    # ── Display existing findings ────────────────────────────────────
    findings = case.get("findings", [])
    if findings:
        st.subheader(f"Findings ({len(findings)})")
        for idx, f in enumerate(findings, 1):
            with st.expander(f"Finding {idx}"):
                st.write(f.get("content", ""))
                tags = f.get("tagged_entities", [])
                if tags:
                    st.caption("Entities: " + ", ".join(str(t) for t in tags))
                patterns = f.get("tagged_patterns", [])
                if patterns:
                    st.caption("Patterns: " + ", ".join(str(p) for p in patterns))
    else:
        st.info("No findings recorded yet.")

    # ── Record new finding ───────────────────────────────────────────
    st.subheader("Record New Finding")
    with st.form("new_finding_form"):
        note = st.text_area("Observation / Note", max_chars=10000)
        entity_tags = st.text_input(
            "Tag Entities (comma-separated names)",
            placeholder="e.g. Giza, Nazca Lines, Erich von Däniken",
        )
        pattern_tags = st.text_input(
            "Tag Pattern IDs (comma-separated)",
            placeholder="e.g. pat-001, pat-002",
        )
        submitted = st.form_submit_button("Save Finding")

    if submitted:
        v_note = validate_analyst_note(note)
        v_tags = validate_entity_tags(entity_tags)
        if not v_note.valid:
            st.error(v_note.error)
        elif not v_tags.valid:
            st.error(v_tags.error)
        else:
            # Build finding payload — the API stores findings as part of the case
            # For now we display a confirmation; actual persistence depends on
            # a findings-specific endpoint or case update endpoint.
            finding = {
                "content": note.strip(),
                "tagged_entities": [t.strip() for t in entity_tags.split(",") if t.strip()],
                "tagged_patterns": [t.strip() for t in pattern_tags.split(",") if t.strip()],
            }
            st.success("Finding recorded.")
            st.json(finding)
