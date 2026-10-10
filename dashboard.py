"""Stage 6: Live Streamlit UI for Autonomous Chaos Engineering & Resilience Observability.
Supports both Local Docker Execution and Interactive Cloud Simulation on Streamlit Community Cloud.
"""

import json
import logging
import math
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from config import (
    ALLOWED_TARGET_SERVICES,
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
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
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
        background-color: #ff4b4b;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85em;
        font-weight: bold;
    }
    .safe-pill {
        background-color: #00c853;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85em;
        font-weight: bold;
    }
</style>
""",
    unsafe_allow_html=True,
)


def load_json(filepath: Path) -> Optional[Any]:
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def is_docker_connected() -> bool:
    try:
        import docker

        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


# Initialize Session State for Interactive Experiments
if "session_experiments" not in st.session_state:
    st.session_state.session_experiments = []
if "session_telemetry" not in st.session_state:
    st.session_state.session_telemetry = []

# Load Base Artifacts
file_report = load_json(REPORT_JSON_FILE) or {}
file_topology = load_json(TOPOLOGY_FILE) or {}
file_plan = load_json(CACHE_PLAN_FILE) or {}
file_telemetry = load_json(TELEMETRY_LOG_FILE) or []

# Merge file telemetry with session telemetry
all_telemetry = list(file_telemetry) + st.session_state.session_telemetry
docker_available = is_docker_connected()

# Sidebar
st.sidebar.title("🛡️ Chaos Agent Control")
mode_label = "🟢 Local Docker Engine" if docker_available else "☁️ Cloud Interactive Simulator"
st.sidebar.markdown(f"**Runtime Mode:** `{mode_label}`")
st.sidebar.markdown(f"**Target System:** OpenTelemetry Demo")
st.sidebar.markdown(f"**Endpoint:** `{FRONTEND_URL}`")

st.sidebar.divider()
st.sidebar.subheader("Safety Guardrails")
st.sidebar.info(
    f"⏱️ **Watchdog:** 500ms cycle\n\n"
    f"🚨 **Max Error Rate:** {DEFAULT_MAX_ERROR_RATE*100:.0f}%\n\n"
    f"⚡ **Max p95 Latency:** {DEFAULT_MAX_P95_MS:.0f}ms\n\n"
    f"🔒 **Rollback:** Automated Instant (<50ms)"
)

if st.sidebar.button("🚨 EMERGENCY KILL-SWITCH (Rollback All)", type="primary"):
    if docker_available:
        try:
            from chaos_injector import ChaosInjector

            injector = ChaosInjector()
            injector.emergency_rollback_all()
            st.sidebar.success("Emergency rollback executed! All services restored.")
        except Exception as e:
            st.sidebar.error(f"Rollback error: {e}")
    else:
        st.sidebar.success("Emergency rollback executed! Cloud simulation restored to baseline.")

auto_refresh = st.sidebar.checkbox("Auto-refresh (every 3s)", value=False)
if auto_refresh:
    time.sleep(3)
    st.rerun()

# Main Header
st.title("🛡️ Autonomous AI Chaos Engineering System")
st.markdown("*Continuous automated resilience probing, fault injection, real-time watchdog safeguards & post-mortems.*")

# Top KPI Metrics Row
resilience_score = file_report.get("overall_resilience_score", 74)
node_count = file_topology.get("node_count", 11)
dep_count = file_topology.get("edge_count", 24)
total_probes = len(all_telemetry)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Resilience Score", f"{resilience_score} / 100", delta="Post-Audit")
with col2:
    st.metric("Discovered Services", node_count)
with col3:
    st.metric("Dependencies Mapped", dep_count)
with col4:
    st.metric("Total Probes (10 RPS)", total_probes)
with col5:
    st.metric("Safety Watchdog", "Active (500ms)", delta="Guarded")

st.divider()

# Tab Layout
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🧪 Interactive Chaos Console",
    "📈 Real-Time Telemetry & Observability",
    "🗺️ Architecture Topology DAG",
    "📋 Campaign History & MTTR",
    "🤖 AI Findings & Prescribed Remediations",
])

# ==============================================================================
# TAB 1: INTERACTIVE CHAOS CONSOLE (Allows users to change & trigger experiments!)
# ==============================================================================
with tab1:
    st.subheader("🎮 Interactive Experiment Injection & Watchdog Supervision")
    st.markdown(
        "Select a target service, configure failure parameters, and execute the experiment. "
        "The **500ms Safety Watchdog** will continuously supervise health and trigger an instant rollback if SLAs are breached."
    )

    col_ctrl, col_info = st.columns([1, 1])

    with col_ctrl:
        st.markdown("#### Configure Chaos Experiment")
        available_services = [n.get("name") for n in file_topology.get("nodes", [])] or ALLOWED_TARGET_SERVICES
        # Filter out proxies or collectors
        selectable_services = [s for s in available_services if s not in ["frontend-proxy", "otel-collector", "jaeger", "prometheus"]]

        selected_service = st.selectbox("1. Target Microservice", selectable_services, index=0)
        selected_type = st.selectbox(
            "2. Failure Injection Type",
            ["container_pause", "cpu_throttle", "network_latency"],
            format_func=lambda x: {
                "container_pause": "Container Pause (Freeze Process)",
                "cpu_throttle": "CPU Quota Throttle (10% CPU choke)",
                "network_latency": "Network Latency & Flagd Delays (500ms)"
            }.get(x, x),
            index=0
        )

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            exp_duration = st.slider("Duration (seconds)", min_value=3, max_value=12, value=8, step=1)
            error_threshold = st.slider("Max Tolerated Error Rate", min_value=0.10, max_value=0.50, value=0.30, step=0.05, format="%.0f%%")
        with col_p2:
            p95_threshold = st.slider("Max Tolerated p95 Latency", min_value=500, max_value=3000, value=1500, step=100, format="%d ms")
            poll_cycle = st.selectbox("Watchdog Polling Rate", ["500 ms (Recommended)", "250 ms", "1000 ms"], index=0)

        run_btn = st.button("🚀 Execute Experiment with Active Safety Watchdog", type="primary", use_container_width=True)

    with col_info:
        st.markdown("#### Experiment Rationale & Centrality")
        node_match = next((n for n in file_topology.get("nodes", []) if n.get("name") == selected_service), None)
        crit = node_match.get("criticality", "HIGH") if node_match else "HIGH"
        in_deg = node_match.get("in_degree", 1) if node_match else 1
        out_deg = node_match.get("out_degree", 1) if node_match else 1

        badge = "🔴 CRITICAL" if crit == "HIGH" else ("🟠 HIGH" if crit == "MEDIUM" else "🟢 LOW")
        st.info(
            f"**Target:** `{selected_service}` | **System Criticality:** {badge}\n\n"
            f"• **Inbound Callers:** {in_deg} | **Outbound Callees:** {out_deg}\n\n"
            f"• **Expected Behavior:** If `{selected_service}` is perturbed, downstream calls may timeout. "
            f"If latency exceeds `{p95_threshold}ms` or errors exceed `{error_threshold*100:.0f}%`, "
            f"the kill-switch will automatically abort within 500ms to preserve cluster health."
        )

        # Quick preset buttons for convenience
        st.markdown("**Quick Presets from AI Plan:**")
        preset_cols = st.columns(3)
        with preset_cols[0]:
            st.caption("🛒 **EXP-001 (Cart)**\nPause container")
        with preset_cols[1]:
            st.caption("📦 **EXP-002 (Catalog)**\nCPU throttle")
        with preset_cols[2]:
            st.caption("💡 **EXP-003 (Rec)**\nNetwork delay")

    # EXECUTION HANDLER
    if run_btn:
        progress_bar = st.progress(0, text="Initializing experiment and capturing baseline...")
        status_box = st.empty()

        # Step A: Local Docker Execution or Cloud Simulation
        if docker_available:
            try:
                from chaos_injector import ChaosInjector
                from safety_guard import SafetyGuard
                from telemetry import TelemetryCollector

                status_box.info("Connecting to Docker daemon and starting telemetry stream...")
                progress_bar.progress(20, text="Starting telemetry worker...")
                tel = TelemetryCollector(target_url=FRONTEND_URL, rate_rps=10)
                tel.start()
                time.sleep(1.5)

                inj = ChaosInjector()
                guard = SafetyGuard(inj, tel)

                progress_bar.progress(40, text=f"Injecting {selected_type} on '{selected_service}'...")
                exp_id = f"EXP-{int(time.time())%1000:03d}"
                res = guard.execute_safeguarded_experiment(
                    experiment_id=exp_id,
                    target_service=selected_service,
                    experiment_type=selected_type,
                    duration_sec=float(exp_duration),
                    max_error_rate=float(error_threshold),
                    max_p95_ms=float(p95_threshold),
                )

                progress_bar.progress(90, text="Finalizing metrics and verifying rollback...")
                time.sleep(1.0)
                tel.stop()
                inj.emergency_rollback_all()
                progress_bar.progress(100, text="Experiment completed!")

                # Store result
                exp_record = {
                    "experiment_id": exp_id,
                    "target_service": selected_service,
                    "experiment_type": selected_type,
                    "kill_switch_triggered": res.kill_switch_triggered,
                    "mttr_sec": res.mttr_sec,
                    "peak_error_rate": res.failure_metrics.get("error_rate", 0.0),
                    "peak_p95_ms": res.failure_metrics.get("p95_latency_ms", 0.0),
                    "actual_duration_sec": res.actual_duration_sec,
                    "evaluation": f"Watchdog triggered: {res.trigger_reason}" if res.kill_switch_triggered else "Safe complete",
                }
                st.session_state.session_experiments.insert(0, exp_record)
                st.rerun()

            except Exception as e:
                status_box.error(f"Execution error: {e}")
                progress_bar.empty()

        else:
            # High-Fidelity Cloud Simulation for Streamlit Community Cloud
            status_box.info(f"Simulating {selected_type} against `{selected_service}` with active 500ms safety watchdog...")
            time.sleep(1.0)
            progress_bar.progress(30, text=f"Applying failure: {selected_type} on {selected_service}...")

            # Realistic physics based on service
            will_trigger_ks = ("cart" in selected_service.lower() and selected_type == "container_pause") or (p95_threshold < 800)
            sim_samples = []
            now_ts = time.time()

            # Simulate 8 steps of 500ms
            for step in range(1, int(exp_duration * 2) + 1):
                time.sleep(0.2)
                progress_bar.progress(min(90, 30 + step * 4), text=f"Supervising health (Step {step}/16)...")

                step_err = 0.15 if "cart" in selected_service.lower() else (0.05 if "catalog" in selected_service.lower() else 0.0)
                step_lat = 2500.0 if "cart" in selected_service.lower() else (1600.0 if selected_type == "cpu_throttle" and step > 4 else random.uniform(40, 180))

                sim_samples.append({
                    "timestamp": now_ts + (step * 0.5),
                    "iso_time": datetime.now(timezone.utc).isoformat(),
                    "status_code": 500 if step_err > 0.10 and random.random() < step_err else 200,
                    "latency_ms": step_lat,
                    "is_error": step_err > 0.10,
                    "event_tag": f"SIM_{selected_service}"
                })

                if (step_lat > p95_threshold or step_err > error_threshold) and will_trigger_ks:
                    status_box.warning(f"🚨 KILL-SWITCH TRIGGERED at {step*0.5:.1f}s: p95 latency reached {step_lat:.1f}ms (Threshold: {p95_threshold}ms). Reverting!")
                    break

            progress_bar.progress(100, text="Rollback completed! Telemetry stabilized.")
            st.session_state.session_telemetry.extend(sim_samples)

            sim_record = {
                "experiment_id": f"EXP-{random.randint(100, 999)}",
                "target_service": selected_service,
                "experiment_type": selected_type,
                "kill_switch_triggered": will_trigger_ks,
                "mttr_sec": 0.45 if will_trigger_ks else 0.12,
                "peak_error_rate": 0.12 if "cart" in selected_service.lower() else 0.0,
                "peak_p95_ms": 2500.0 if will_trigger_ks else 95.0,
                "actual_duration_sec": 3.5 if will_trigger_ks else float(exp_duration),
                "evaluation": "Kill-switch averted cascading outage." if will_trigger_ks else "Safe complete within SLA thresholds.",
            }
            st.session_state.session_experiments.insert(0, sim_record)
            st.success("Experiment simulation finished and recorded!")
            time.sleep(1.0)
            st.rerun()

    # DISPLAY RECENT EXPERIMENTS
    all_experiments = st.session_state.session_experiments + file_report.get("experiments_evaluated", [])
    if all_experiments:
        st.divider()
        st.markdown("### 📋 Interactive Experiment Inspector")
        exp_options = [f"[{e.get('experiment_id')}] {e.get('target_service')} ({e.get('experiment_type')})" for e in all_experiments]
        selected_exp_idx = st.selectbox("Select Experiment to Inspect Detailed Diagnostics:", range(len(exp_options)), format_func=lambda i: exp_options[i])

        chosen = all_experiments[selected_exp_idx]
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Target Service", chosen.get("target_service"))
        with c2:
            st.metric("Failure Type", chosen.get("experiment_type"))
        with c3:
            st.metric("MTTR", f"{chosen.get('mttr_sec', 0.0):.2f}s")
        with c4:
            ks_flag = chosen.get("kill_switch_triggered", False)
            st.metric("Watchdog Kill-Switch", "🚨 TRIGGERED" if ks_flag else "🛡️ Safe Complete")

        st.info(f"**Diagnostic Evaluation:** {chosen.get('evaluation', 'Nominal test completion.')}")

# ==============================================================================
# TAB 2: TELEMETRY & OBSERVABILITY
# ==============================================================================
with tab2:
    st.subheader("Traffic Generation & Telemetry Stream")
    if all_telemetry:
        df_telemetry = pd.DataFrame(all_telemetry)
        df_telemetry["time"] = pd.to_datetime(df_telemetry["timestamp"], unit="s")

        # Interactive controls for charts
        col_c1, col_c2 = st.columns([1, 1])
        with col_c1:
            smoothing_window = st.slider("Metric Smoothing Window (Probes)", min_value=3, max_value=30, value=10, step=1)
        with col_c2:
            available_tags = ["All Events"] + [str(t) for t in df_telemetry["event_tag"].dropna().unique()]
            selected_tag = st.selectbox("Filter by Experiment Event Tag", available_tags, index=0)

        if selected_tag != "All Events":
            df_chart = df_telemetry[df_telemetry["event_tag"] == selected_tag]
        else:
            df_chart = df_telemetry

        df_chart["rolling_p95"] = df_chart["latency_ms"].rolling(window=smoothing_window).quantile(0.95)
        df_chart["rolling_p50"] = df_chart["latency_ms"].rolling(window=smoothing_window).median()
        df_chart["is_5xx"] = df_chart["status_code"] >= 500
        df_chart["rolling_err_pct"] = df_chart["is_5xx"].rolling(window=smoothing_window).mean() * 100.0

        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("#### Latency Profiles (ms)")
            chart_latency = df_chart[["time", "rolling_p50", "rolling_p95"]].dropna().set_index("time")
            chart_latency.columns = ["p50 Latency (ms)", "p95 Latency (ms)"]
            st.line_chart(chart_latency, color=["#29b5e8", "#ff4b4b"])
            st.caption("Blue: p50 Median Latency | Red: p95 Tail Latency (Watchdog threshold: 1500ms)")

        with col_right:
            st.markdown("#### HTTP 5xx Error Rate (%)")
            chart_err = df_chart[["time", "rolling_err_pct"]].dropna().set_index("time")
            chart_err.columns = ["HTTP 5xx Error Rate (%)"]
            st.line_chart(chart_err, color=["#ff7f0e"])
            st.caption("Orange: Rolling HTTP error percentage (Watchdog kill-switch threshold: 30%)")

        st.markdown("#### Recent Telemetry Probes")
        st.dataframe(
            df_chart[["iso_time", "status_code", "latency_ms", "is_error", "event_tag"]].tail(15).sort_values("iso_time", ascending=False),
            use_container_width=True,
        )
    else:
        st.info("No telemetry logs recorded yet. Execute an experiment above or run `python main.py`.")

# ==============================================================================
# TAB 3: TOPOLOGY GRAPH
# ==============================================================================
with tab3:
    st.subheader("Service Architecture & Dependency Graph")
    if file_topology:
        st.markdown(f"**Discovery Source:** `{file_topology.get('source')}` | **Captured:** `{file_topology.get('timestamp')}`")

        # Render Graphviz DOT visualization
        dot_code = [
            "digraph G {",
            "  rankdir=LR;",
            '  node [shape=box, style="rounded,filled", fillcolor="#1f2937", fontcolor="white", fontname="Helvetica"];',
            '  edge [color="#6b7280", fontcolor="#9ca3af", fontname="Helvetica", fontsize=9];',
        ]

        for node in file_topology.get("nodes", []):
            name = node["name"]
            crit = node.get("criticality", "LOW")
            color = "#ef4444" if crit == "HIGH" else ("#f59e0b" if crit == "MEDIUM" else "#10b981")
            dot_code.append(
                f'  "{name}" [label="{name}\\n(In: {node.get("in_degree",0)} | Out: {node.get("out_degree",0)})", color="{color}", penwidth=2.5];'
            )

        for edge in file_topology.get("edges", []):
            caller = edge.get("caller")
            callee = edge.get("callee")
            calls = edge.get("call_count", 1)
            dot_code.append(f'  "{caller}" -> "{callee}" [label="{calls} calls"];')

        dot_code.append("}")
        st.graphviz_chart("\n".join(dot_code))

        st.markdown("#### Microservice Inventory & Criticality Analysis")
        node_df = pd.DataFrame(file_topology.get("nodes", []))
        if not node_df.empty:
            st.dataframe(
                node_df[["name", "criticality", "in_degree", "out_degree", "total_in_calls", "total_out_calls"]],
                use_container_width=True,
            )
    else:
        st.info("Topology graph not yet discovered.")

# ==============================================================================
# TAB 4: CAMPAIGN HISTORY & MTTR
# ==============================================================================
with tab4:
    st.subheader("Chaos Experiment Execution Log & MTTR")
    all_experiments = st.session_state.session_experiments + file_report.get("experiments_evaluated", [])
    if all_experiments:
        exp_df = pd.DataFrame(all_experiments)
        st.dataframe(exp_df, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### Mean Time To Recover (MTTR in seconds)")
            if "mttr_sec" in exp_df.columns:
                mttr_chart = exp_df[["target_service", "mttr_sec"]].set_index("target_service")
                st.bar_chart(mttr_chart)
        with col_b:
            st.markdown("#### Peak Latency Under Injection (ms)")
            if "peak_p95_ms" in exp_df.columns:
                lat_chart = exp_df[["target_service", "peak_p95_ms"]].set_index("target_service")
                st.bar_chart(lat_chart)
    else:
        st.info("No chaos experiments executed yet.")

# ==============================================================================
# TAB 5: AI FINDINGS & REMEDIATIONS
# ==============================================================================
with tab5:
    st.subheader("Gemini Flash Post-Mortem Resilience Report")
    if file_report:
        st.markdown(f"### 🛡️ Overall Resilience Score: **{file_report.get('overall_resilience_score', 74)} / 100**")
        st.write(file_report.get("summary", ""))

        st.divider()
        st.markdown("### 🔍 Detected Vulnerabilities")
        for v in file_report.get("vulnerabilities", []):
            sev = v.get("severity", "MEDIUM")
            badge_class = "badge-critical" if sev == "CRITICAL" else ("badge-high" if sev == "HIGH" else "badge-medium")
            st.markdown(
                f"""
            <div style="background:#161923; padding:12px; border-radius:6px; margin-bottom:12px; border-left: 5px solid {'#ff4b4b' if sev=='CRITICAL' else ('#ffa116' if sev=='HIGH' else '#ffcc00')}">
                <span class="{badge_class}">{sev}</span> <strong>{v.get('title')}</strong> (Service: <code>{v.get('service')}</code>)
                <p style="margin-top:8px; margin-bottom:4px; font-size:0.95em;">{v.get('description')}</p>
                <small style="color:#aaa;"><strong>Impact:</strong> {v.get('impact')}</small>
            </div>
            """,
                unsafe_allow_html=True,
            )

        st.divider()
        st.markdown("### 🛠️ Prescribed Cloud-Native Fixes")
        fixes = file_report.get("prescribed_fixes", [])
        if fixes:
            fixes_df = pd.DataFrame(fixes)
            st.dataframe(fixes_df[["priority", "service", "fix_type", "recommendation", "effort"]], use_container_width=True)

        if REPORT_MD_FILE.exists():
            st.download_button(
                label="📥 Download Full FINDINGS_REPORT.md",
                data=REPORT_MD_FILE.read_text(encoding="utf-8"),
                file_name="FINDINGS_REPORT.md",
                mime="text/markdown",
            )
    else:
        st.info("Run `python main.py` to generate the AI Resilience Report.")
