"""Case File Detail and Ingestion page.

Displays case metadata, ingestion status, entity/relationship counts.
Provides a document upload form that triggers the ingestion API.

Requirements: 6.1, 2.1
"""

import base64

import streamlit as st

import api_client
from validation import validate_topic_name


def render():
    st.markdown("## 📁 Case Detail")

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

    # ── Fetch case metadata ──────────────────────────────────────────
    try:
        case = api_client.get_case_file(case_id)
    except api_client.APIError as exc:
        st.error(f"Could not load case: {exc.detail}")
        return
    except Exception as exc:
        st.error(f"Could not load case: {exc}")
        return

    # ── Display metadata ─────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric("Status", case.get("status", ""))
    col2.metric("Documents", case.get("document_count", 0))
    col3.metric("Entities", case.get("entity_count", 0))

    col4, col5 = st.columns(2)
    col4.metric("Relationships", case.get("relationship_count", 0))
    col5.metric("Created", case.get("created_at", "")[:10])

    st.markdown(f"**Topic:** {case.get('topic_name', '')}")
    st.markdown(f"**Description:** {case.get('description', '')}")

    if case.get("parent_case_id"):
        st.markdown(f"**Parent Case:** {case['parent_case_id']}")
    if case.get("error_details"):
        st.warning(f"Error: {case['error_details']}")

    # ── Actions ──────────────────────────────────────────────────────
    act_col1, act_col2 = st.columns(2)
    with act_col1:
        if st.button("Archive Case"):
            try:
                api_client.archive_case_file(case_id.strip())
                st.success("Case archived.")
                st.rerun()
            except api_client.APIError as exc:
                st.error(f"Archive failed: {exc.detail}")
    with act_col2:
        if st.button("Delete Case", type="primary"):
            try:
                api_client.delete_case_file(case_id.strip())
                st.success("Case deleted.")
            except api_client.APIError as exc:
                st.error(f"Delete failed: {exc.detail}")

    # ── Upload documents for ingestion ───────────────────────────────
    st.subheader("Ingest Documents")
    uploaded_files = st.file_uploader(
        "Upload files for ingestion",
        accept_multiple_files=True,
    )

    if st.button("Start Ingestion") and uploaded_files:
        files_payload = []
        for uf in uploaded_files:
            content = uf.read()
            files_payload.append({
                "filename": uf.name,
                "content_base64": base64.b64encode(content).decode("utf-8"),
            })
        try:
            result = api_client.ingest_documents(case_id.strip(), files_payload)
            st.success(
                f"Ingestion complete — {result.get('successful', 0)} succeeded, "
                f"{result.get('failed', 0)} failed out of {result.get('total_documents', 0)}."
            )
            if result.get("failures"):
                for f in result["failures"]:
                    st.warning(f"Failed: {f.get('document_id', '?')} — {f.get('error', '')}")
        except api_client.APIError as exc:
            st.error(f"Ingestion failed: {exc.detail}")
