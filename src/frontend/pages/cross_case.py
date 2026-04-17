"""Cross-Case Analysis page.

Select cases for cross-reference, display cross-reference reports,
manage cross-case graphs (create, add/remove members, view).

Requirements: 5.2, 5.4, 5.6, 5.8, 5.9, 5.10
"""

import streamlit as st

import api_client
from validation import validate_graph_name


def render():
    st.header("Cross-Case Analysis")

    # ── Cross-reference analysis ─────────────────────────────────────
    st.subheader("Run Cross-Reference Analysis")
    case_ids_input = st.text_area(
        "Case IDs (one per line, minimum 2)",
        height=100,
        key="cross_case_ids",
    )

    if st.button("Analyze"):
        ids = [cid.strip() for cid in case_ids_input.strip().splitlines() if cid.strip()]
        if len(ids) < 2:
            st.error("Provide at least 2 case IDs.")
        else:
            with st.spinner("Running cross-case analysis..."):
                try:
                    report = api_client.analyze_cross_case(ids)
                    _display_cross_report(report)
                except api_client.APIError as exc:
                    st.error(f"Analysis failed: {exc.detail}")

    st.divider()

    # ── Create cross-case graph ──────────────────────────────────────
    st.subheader("Create Cross-Case Graph")
    with st.form("create_graph_form"):
        graph_name = st.text_input("Graph Name", max_chars=255)
        graph_case_ids = st.text_area(
            "Case IDs (one per line, minimum 2)",
            height=100,
        )
        create_submitted = st.form_submit_button("Create Graph")

    if create_submitted:
        v_name = validate_graph_name(graph_name)
        if not v_name.valid:
            st.error(v_name.error)
        else:
            ids = [cid.strip() for cid in graph_case_ids.strip().splitlines() if cid.strip()]
            if len(ids) < 2:
                st.error("Provide at least 2 case IDs.")
            else:
                try:
                    result = api_client.create_cross_case_graph(graph_name.strip(), ids)
                    st.success(f"Graph created: {result.get('graph_id', '')}")
                except api_client.APIError as exc:
                    st.error(f"Creation failed: {exc.detail}")

    st.divider()

    # ── View / manage existing graph ─────────────────────────────────
    st.subheader("Manage Cross-Case Graph")
    graph_id = st.text_input("Graph ID", key="manage_graph_id")

    if graph_id:
        try:
            graph = api_client.get_cross_case_graph(graph_id.strip())
            st.json(graph)
        except api_client.APIError as exc:
            st.error(f"Could not load graph: {exc.detail}")
            return

        # Add / remove members
        with st.form("update_graph_form"):
            add_ids = st.text_input("Add Case IDs (comma-separated)")
            remove_ids = st.text_input("Remove Case IDs (comma-separated)")
            update_submitted = st.form_submit_button("Update Membership")

        if update_submitted:
            add_list = [c.strip() for c in add_ids.split(",") if c.strip()] if add_ids else None
            remove_list = [c.strip() for c in remove_ids.split(",") if c.strip()] if remove_ids else None
            if not add_list and not remove_list:
                st.warning("Provide case IDs to add or remove.")
            else:
                try:
                    result = api_client.update_cross_case_graph(
                        graph_id.strip(),
                        add_case_ids=add_list,
                        remove_case_ids=remove_list,
                    )
                    st.success("Graph membership updated.")
                    st.json(result)
                except api_client.APIError as exc:
                    st.error(f"Update failed: {exc.detail}")


def _display_cross_report(report: dict):
    """Render a cross-reference report."""
    st.markdown(f"**Report ID:** {report.get('report_id', '?')}")
    st.markdown(f"**Cases:** {', '.join(report.get('case_ids', []))}")

    shared = report.get("shared_entities", [])
    if shared:
        st.markdown(f"**Shared Entities ({len(shared)}):**")
        for match in shared:
            ea = match.get("entity_a", {})
            eb = match.get("entity_b", {})
            st.write(
                f"- {ea.get('name', '?')} ↔ {eb.get('name', '?')} "
                f"(similarity: {match.get('similarity_score', 0):.2f})"
            )
            if match.get("ai_explanation"):
                st.caption(match["ai_explanation"])

    if report.get("ai_analysis"):
        st.markdown("**AI Analysis:**")
        st.write(report["ai_analysis"])
