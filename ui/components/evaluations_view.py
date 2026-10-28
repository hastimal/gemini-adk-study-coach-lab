"""Evaluations UI Component for Streamlit.

Renders interactive evaluations runner, scenario list, pass/fail status,
latency metrics, per-scenario expandable details, error messaging, and report history.
"""

from typing import Any

import streamlit as st

from study_coach.evaluation import (
    EvaluationRunner,
    load_evaluation_report,
)


def render_evaluations_tab(runner: EvaluationRunner, run_async_fn: Any) -> None:
    """Renders the Evaluations management and reporting view."""
    st.header("🧪 Agent Evaluations Suite")
    st.write(
        "Execute automated evaluations across Topic Expert, Quiz Generator, Study Planner, "
        "and Root Coordinator agents to verify reasoning quality, latency budgets, and schema fidelity."
    )

    # Action Toolbar
    col_btn, col_info = st.columns([1, 3])

    is_running = runner.is_running()

    with col_btn:
        button_disabled = bool(
            is_running or st.session_state.get("_eval_in_progress", False)
        )
        if st.button(
            "🚀 Run Evaluations",
            type="primary",
            use_container_width=True,
            disabled=button_disabled,
            help="Executes 4 live ADK scenarios against current Gemini model.",
        ):
            st.session_state["_eval_in_progress"] = True
            with st.spinner(
                "Executing 4 agent evaluation scenarios via Google ADK... (takes ~60-90s)"
            ):
                try:
                    report, already_running = run_async_fn(runner.run_all(persist=True))
                    if already_running:
                        st.warning(
                            "⚠️ An evaluation run is already currently executing."
                        )
                    elif report.failed_scenarios > 0:
                        st.error(
                            f"Evaluations completed with errors: {report.passed_scenarios}/{report.total_scenarios} passed."
                        )
                    else:
                        st.success(
                            f"All {report.passed_scenarios}/{report.total_scenarios} evaluation scenarios passed! ({report.total_duration_seconds:.2f}s)"
                        )
                except (RuntimeError, ValueError, TimeoutError, OSError) as err:
                    st.error(f"Error during evaluation execution: {err}")
                finally:
                    st.session_state["_eval_in_progress"] = False
            st.rerun()

    with col_info:
        if is_running or st.session_state.get("_eval_in_progress", False):
            st.info("⏳ Evaluation run is currently in progress. Please wait...")
        else:
            st.caption(
                "Click 'Run Evaluations' to evaluate all 4 scenarios. "
                "Results are saved to `docs/reports/recent_evaluation_report.json` without PII or secret keys."
            )

    st.markdown("---")

    # Load recent report
    report = load_evaluation_report()

    if not report:
        st.info(
            "ℹ️ No evaluations yet. Click **Run Evaluations** above to start the test suite."
        )
        return

    # Summary Metrics Row
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)

    with m_col1:
        st.metric(
            "Pass Rate",
            f"{report.passed_scenarios} / {report.total_scenarios}",
            delta="100%"
            if report.failed_scenarios == 0
            else f"-{report.failed_scenarios} failed",
            delta_color="normal" if report.failed_scenarios == 0 else "inverse",
        )

    with m_col2:
        st.metric("Total Latency", f"{report.total_duration_seconds:.2f}s")

    with m_col3:
        st.metric("Evaluated Model", report.model)

    with m_col4:
        # Display readable timestamp
        ts_clean = report.timestamp.split(".")[0].replace("T", " ")
        st.metric("Last Run (UTC)", ts_clean)

    st.markdown("### 📋 Scenario Results")

    for scenario in report.scenarios:
        status_icon = "✅ PASS" if scenario.status == "PASS" else "❌ FAIL"
        expander_title = (
            f"{status_icon} [{scenario.scenario_id}] {scenario.target_agent} — "
            f"{scenario.duration_seconds:.2f}s"
        )

        with st.expander(expander_title, expanded=(scenario.status == "FAIL")):
            col_left, col_right = st.columns([2, 1])

            with col_left:
                st.markdown(f"**Description:** {scenario.scenario_description}")
                st.markdown(f"**Target Agent:** `{scenario.target_agent}`")
                st.markdown(f"**Status:** `{scenario.status}`")
                if scenario.failure_category and scenario.failure_category != "none":
                    st.markdown(
                        f"**Failure Category:** :red-background[`{scenario.failure_category}`]"
                    )
                st.markdown(f"**Measured Latency:** `{scenario.duration_seconds:.2f}s`")

                if scenario.details:
                    st.info(f"**Details:** {scenario.details}")

                if scenario.error:
                    st.error(f"**Error Details:** {scenario.error}")

            with col_right:
                if scenario.metadata:
                    st.markdown("**Structured Metadata:**")
                    st.json(scenario.metadata)
                else:
                    st.caption("No extra metadata recorded.")

    st.markdown("---")
    with st.expander("📄 Raw Report JSON (Sanitized)"):
        st.json(report.model_dump())
