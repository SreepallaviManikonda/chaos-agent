"""Stage 6: Live Streamlit UI for Autonomous Chaos Engineering & Resilience Observability."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from config import (
    CACHE_PLAN_FILE,
    DEFAULT_MAX_ERROR_RATE,
    DEFAULT_MAX_P95_MS,
    FRONTEND_URL,
    REPORT_JSON_FILE,
    REPORT_MD_FILE,
    TELEMETRY_LOG_FILE,
    TOPOLOGY_FILE,
)

st.set_page_config(
    page_title="AI Chaos Engineering & Resilience Console",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1e2130;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #2e344e;
    }
    .badge-critical {
        background-color: #ff4b4b;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-high {
        background-color: #ffa116;
        color: black;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-medium {
        background-color: #ffcc00;
        color: black;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .killswitch-pill {
        background-color: #00c853;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85em;
    }
</style>
""", unsafe_allow_html=True)


def load_json(filepath: Path) -> Optional[Any]:
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


# Sidebar
st.sidebar.title("🛡️ Chaos Agent Control")
st.sidebar.markdown(f"**Target System:** OpenTelemetry Demo")
st.sidebar.markdown(f"**Endpoint:** `{FRONTEND_URL}`")
st.sidebar.markdown("**Engine:** Gemini 2.5 Flash + Docker-py")

st.sidebar.divider()
st.sidebar.subheader("Safety Guardrails")
st.sidebar.info(
    f"⏱️ **Watchdog:** 500ms cycle\n\n"
    f"🚨 **Max Error Rate:** {DEFAULT_MAX_ERROR_RATE*100:.0f}%\n\n"
    f"⚡ **Max p95 Latency:** {DEFAULT_MAX_P95_MS:.0f}ms\n\n"
    f"🔒 **Rollback:** Automated Instant"
)

if st.sidebar.button("🚨 EMERGENCY KILL-SWITCH (Rollback All)", type="primary"):
    try:
        from chaos_injector import ChaosInjector
        injector = ChaosInjector()
        injector.emergency_rollback_all()
        st.sidebar.success("Emergency rollback executed! All services unpaused.")
    except Exception as e:
        st.sidebar.error(f"Rollback error: {e}")

auto_refresh = st.sidebar.checkbox("Auto-refresh data (every 3s)", value=False)
if auto_refresh:
    time.sleep(3)
    st.rerun()

# Main Header
st.title("🛡️ Autonomous AI Chaos Engineering System")
st.markdown("*Continuous automated resilience probing, fault injection, real-time watchdog safeguards & post-mortems.*")

# Top KPI Metrics Row
report_data = load_json(REPORT_JSON_FILE)
topology_data = load_json(TOPOLOGY_FILE)
telemetry_data = load_json(TELEMETRY_LOG_FILE) or []

resilience_score = report_data.get("overall_resilience_score", 0) if report_data else 0
score_color = "normal" if resilience_score >= 80 else "inverse"

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Resilience Score", f"{resilience_score} / 100" if report_data else "Pending Run", delta="Post-Audit" if report_data else None)
with col2:
    node_count = topology_data.get("node_count", 0) if topology_data else 0
    st.metric("Discovered Services", node_count)
with col3:
    dep_count = topology_data.get("edge_count", 0) if topology_data else 0
    st.metric("Dependencies Mapped", dep_count)
with col4:
    total_probes = len(telemetry_data)
    st.metric("Total Probes (10 RPS)", total_probes)
with col5:
    status_label = "Active & Guarded" if telemetry_data else "Standby"
    st.metric("System Status", status_label)

st.divider()

# Tab Layout
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Real-Time Observability & Telemetry",
    "🗺️ Discovered Architecture Topology",
    "🧪 Chaos Experiments & Kill-Switch Log",
    "🤖 AI Findings & Prescribed Remediations"
])

# TAB 1: Telemetry & Observability
with tab1:
    st.subheader("Traffic Generation & Telemetry Stream")
    if telemetry_data:
        df_telemetry = pd.DataFrame(telemetry_data)
        df_telemetry["time"] = pd.to_datetime(df_telemetry["timestamp"], unit="s")

        # Rolling window calculations
        window_size = 10
        df_telemetry["rolling_p95"] = df_telemetry["latency_ms"].rolling(window=window_size).quantile(0.95)
        df_telemetry["rolling_p50"] = df_telemetry["latency_ms"].rolling(window=window_size).median()
        df_telemetry["is_5xx"] = df_telemetry["status_code"] >= 500
        df_telemetry["rolling_err_pct"] = df_telemetry["is_5xx"].rolling(window=window_size).mean() * 100.0

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### Latency Profiles (ms)")
            chart_latency = df_telemetry[["time", "rolling_p50", "rolling_p95"]].dropna().set_index("time")
            chart_latency.columns = ["p50 Latency (ms)", "p95 Latency (ms)"]
            st.line_chart(chart_latency, color=["#29b5e8", "#ff4b4b"])
            st.caption("Blue: p50 Median Latency | Red: p95 Tail Latency (Watchdog threshold: 1200ms)")

        with col_right:
            st.markdown("#### HTTP 5xx Error Rate (%)")
            chart_err = df_telemetry[["time", "rolling_err_pct"]].dropna().set_index("time")
            chart_err.columns = ["HTTP 5xx Error Rate (%)"]
            st.line_chart(chart_err, color=["#ff7f0e"])
            st.caption("Orange: 10-probe rolling HTTP error percentage (Watchdog kill-switch threshold: 30%)")

        st.markdown("#### Recent Probes")
        st.dataframe(
            df_telemetry[["iso_time", "status_code", "latency_ms", "is_error", "event_tag"]].tail(12).sort_values("iso_time", ascending=False),
            use_container_width=True
        )
    else:
        st.info("No telemetry logs recorded yet. Run `python main.py` to start traffic probing and metrics collection.")

# TAB 2: Topology Graph
with tab2:
    st.subheader("Service Architecture & Dependency Graph")
    if topology_data:
        st.markdown(f"**Discovery Source:** `{topology_data.get('source')}` | **Captured:** `{topology_data.get('timestamp')}`")

        # Render Graphviz DOT visualization
        dot_code = ["digraph G {", "  rankdir=LR;", '  node [shape=box, style="rounded,filled", fillcolor="#1f2937", fontcolor="white", fontname="Helvetica"];', '  edge [color="#6b7280", fontcolor="#9ca3af", fontname="Helvetica", fontsize=9];']

        # Highlight nodes
        for node in topology_data.get("nodes", []):
            name = node["name"]
            crit = node.get("criticality", "LOW")
            color = "#ef4444" if crit == "HIGH" else ("#f59e0b" if crit == "MEDIUM" else "#10b981")
            dot_code.append(f'  "{name}" [label="{name}\\n(In: {node.get("in_degree",0)} | Out: {node.get("out_degree",0)})", color="{color}", penwidth=2.0];')

        for edge in topology_data.get("edges", []):
            caller = edge.get("caller")
            callee = edge.get("callee")
            calls = edge.get("call_count", 1)
            dot_code.append(f'  "{caller}" -> "{callee}" [label="{calls} calls"];')

        dot_code.append("}")
        st.graphviz_chart("\n".join(dot_code))

        st.markdown("#### Microservice Inventory & Criticality Analysis")
        node_df = pd.DataFrame(topology_data.get("nodes", []))
        if not node_df.empty:
            st.dataframe(node_df[["name", "criticality", "in_degree", "out_degree", "total_in_calls", "total_out_calls"]], use_container_width=True)
    else:
        st.info("Topology graph not yet discovered. Run `python main.py` or `python topology.py`.")

# TAB 3: Chaos Experiments Log
with tab3:
    st.subheader("Chaos Experiment Execution & Watchdog Interventions")
    plan_data = load_json(CACHE_PLAN_FILE)
    if plan_data:
        st.markdown(f"**Campaign:** `{plan_data.get('plan_name')}`")
        st.caption(plan_data.get("architecture_summary", ""))

    if report_data and "experiments_evaluated" in report_data:
        exp_list = report_data["experiments_evaluated"]
        exp_df = pd.DataFrame(exp_list)
        st.dataframe(exp_df, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### Mean Time To Recover (MTTR)")
            mttr_chart = exp_df[["target_service", "mttr_sec"]].set_index("target_service")
            st.bar_chart(mttr_chart)
        with col_b:
            st.markdown("#### Peak Latency Under Injection (ms)")
            lat_chart = exp_df[["target_service", "peak_p95_ms"]].set_index("target_service")
            st.bar_chart(lat_chart)
    else:
        st.info("No chaos experiments executed yet. Launch `python main.py` to run the test suite.")

# TAB 4: AI Findings & Remediations
with tab4:
    st.subheader("Gemini Flash Post-Mortem Resilience Report")
    if report_data:
        st.markdown(f"### 🛡️ Overall Resilience Score: **{report_data.get('overall_resilience_score')}/100**")
        st.write(report_data.get("summary", ""))

        st.divider()
        st.markdown("### 🔍 Detected Vulnerabilities")
        for v in report_data.get("vulnerabilities", []):
            sev = v.get("severity", "MEDIUM")
            badge_class = "badge-critical" if sev == "CRITICAL" else ("badge-high" if sev == "HIGH" else "badge-medium")
            st.markdown(f"""
            <div style="background:#161923; padding:12px; border-radius:6px; margin-bottom:12px; border-left: 5px solid {'#ff4b4b' if sev=='CRITICAL' else ('#ffa116' if sev=='HIGH' else '#ffcc00')}">
                <span class="{badge_class}">{sev}</span> <strong>{v.get('title')}</strong> (Service: <code>{v.get('service')}</code>)
                <p style="margin-top:8px; margin-bottom:4px; font-size:0.95em;">{v.get('description')}</p>
                <small style="color:#aaa;"><strong>Impact:</strong> {v.get('impact')}</small>
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        st.markdown("### 🛠️ Prescribed Cloud-Native Fixes")
        fixes = report_data.get("prescribed_fixes", [])
        if fixes:
            fixes_df = pd.DataFrame(fixes)
            st.dataframe(fixes_df[["priority", "service", "fix_type", "recommendation", "effort"]], use_container_width=True)

        if REPORT_MD_FILE.exists():
            st.download_button(
                label="📥 Download Full FINDINGS_REPORT.md",
                data=REPORT_MD_FILE.read_text(encoding="utf-8"),
                file_name="FINDINGS_REPORT.md",
                mime="text/markdown"
            )
    else:
        st.info("Run `python main.py` to generate the AI Resilience Report and architectural remedies.")
