"""Semantic Search page.

Natural language query input, display search results with passages,
relevance scores, source refs, and context.

Requirements: 10.2, 10.3
"""

import streamlit as st

import api_client
from validation import validate_search_query, validate_top_k


def render():
    st.markdown("## 🔎 Semantic Search")

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

    with st.form("search_form"):
        query = st.text_area("Search Query", max_chars=1000,
                             placeholder="Enter a natural language question...")
        top_k = st.number_input("Max Results", min_value=1, max_value=100,
                                value=10, step=1)
        submitted = st.form_submit_button("Search")

    if submitted:
        v_query = validate_search_query(query)
        v_topk = validate_top_k(int(top_k))
        if not v_query.valid:
            st.error(v_query.error)
            return
        if not v_topk.valid:
            st.error(v_topk.error)
            return

        with st.spinner("Searching..."):
            try:
                data = api_client.search(case_id.strip(), query.strip(), int(top_k))
                results = data.get("results", [])
            except api_client.APIError as exc:
                st.error(f"Search failed: {exc.detail}")
                return

        if not results:
            st.info("No results found.")
            return

        st.subheader(f"Results ({len(results)})")
        for idx, r in enumerate(results, 1):
            score = r.get("relevance_score", 0)
            st.markdown(f"---\n**{idx}. Relevance: {score:.3f}**")
            st.markdown(f"**Source:** {r.get('source_document_ref', 'N/A')}")
            st.markdown(f"**Passage:**\n> {r.get('passage', '')}")
            if r.get("surrounding_context"):
                with st.expander("Context"):
                    st.write(r["surrounding_context"])
