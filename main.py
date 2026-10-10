"""Stage 7: Master End-to-End Orchestrator for Autonomous AI Chaos Engineering."""

import json
import logging
import sys
import time
from typing import List

from ai_planner import AIChaosPlanner
from ai_reporter import AIReporter
from chaos_injector import ChaosInjector
from config import (
    CACHE_PLAN_FILE,
    FRONTEND_URL,
    REPORT_JSON_FILE,
    REPORT_MD_FILE,
    TELEMETRY_LOG_FILE,
)
from safety_guard import ExperimentResult, SafetyGuard
from telemetry import TelemetryCollector
from topology import TopologyDiscovery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ChaosMasterOrchestrator")


def print_banner() -> None:
    print("\n" + "=" * 80)
    print("      🛡️  AUTONOMOUS AI-DRIVEN CHAOS ENGINEERING SYSTEM  🛡️")
    print("      Cloud-Native Resilience & Automated Kill-Switch Guardrails")
    print("=" * 80 + "\n")


def run_pipeline() -> None:
    """Executes the complete 5-stage Autonomous Chaos Engineering workflow."""
    print_banner()

    # -------------------------------------------------------------
    # STAGE 1: Check Docker Daemon & Environment Health
    # -------------------------------------------------------------
    logger.info(">>> STAGE 1: Verifying Docker Environment & Microservice Health...")
    injector = ChaosInjector()
    if not injector.client:
        logger.error("Could not establish connection to Docker daemon. Ensure Docker is running.")
        sys.exit(1)

    containers = injector.client.containers.list()
    running_names = [c.name for c in containers]
    logger.info(f"Docker connected successfully. Detected {len(containers)} active containers:")
    logger.info(f"Running services sample: {running_names[:10]}...")

    # Run emergency rollback upfront to guarantee pristine initial state
    injector.emergency_rollback_all()

    # -------------------------------------------------------------
    # STAGE 2: Topology & Call Dependency Discovery (Jaeger / Compose)
    # -------------------------------------------------------------
    logger.info("\n>>> STAGE 2: Discovering Architecture Topology via Jaeger Tracing API...")
    discovery = TopologyDiscovery()
    topology = discovery.discover()
    logger.info(
        f"Topology mapping complete! Source: {topology['source']} | "
        f"Discovered {topology['node_count']} microservices and {topology['edge_count']} call edges."
    )

    # -------------------------------------------------------------
    # STAGE 3: Start Real-Time Observability & Baseline Traffic Probing
    # -------------------------------------------------------------
    logger.info(f"\n>>> STAGE 3: Initializing Load Generator against {FRONTEND_URL} (10 RPS)...")
    telemetry = TelemetryCollector(target_url=FRONTEND_URL, rate_rps=10)
    telemetry.start()

    try:
        # Capture 5-second steady-state baseline
        logger.info("Capturing 5-second steady-state baseline metrics...")
        baseline_stats = telemetry.capture_baseline(duration_sec=5.0)
        baseline_dict = {
            "total_requests": baseline_stats.total_requests,
            "error_rate": baseline_stats.error_rate,
            "p50_latency_ms": baseline_stats.p50_latency_ms,
            "p95_latency_ms": baseline_stats.p95_latency_ms,
            "avg_latency_ms": baseline_stats.avg_latency_ms,
        }
        logger.info(
            f"Steady-State Baseline: 5xx Error Rate={baseline_dict['error_rate']*100:.1f}%, "
            f"p50={baseline_dict['p50_latency_ms']:.1f}ms, p95={baseline_dict['p95_latency_ms']:.1f}ms"
        )

        # -------------------------------------------------------------
        # STAGE 4: AI Intelligent Experiment Planning (Gemini 2.5 Flash)
        # -------------------------------------------------------------
        logger.info("\n>>> STAGE 4: Generating Intelligent Chaos Plan with Gemini Flash...")
        planner = AIChaosPlanner()
        chaos_plan = planner.create_plan(topology=topology, force_refresh=False)

        print("\n" + "-" * 70)
        print(f"📋 AI CHAOS PLAN: {chaos_plan.plan_name}")
        print(f"Summary: {chaos_plan.architecture_summary}")
        print(f"Selected Experiments: {len(chaos_plan.experiments)}")
        for idx, exp in enumerate(chaos_plan.experiments, 1):
            print(f"  {idx}. [{exp.id}] {exp.name} -> Target: '{exp.target_service}' ({exp.experiment_type})")
            print(f"     Hypothesis: {exp.hypothesis}")
            print(f"     Thresholds: Error < {exp.max_error_rate*100:.0f}%, p95 < {exp.max_p95_ms:.0f}ms")
        print("-" * 70 + "\n")

        # -------------------------------------------------------------
        # STAGE 5: Safeguarded Experiment Execution & Watchdog Supervision
        # -------------------------------------------------------------
        logger.info(">>> STAGE 5: Executing Sequenced Chaos Experiments with 500ms Safety Watchdog...")
        guard = SafetyGuard(injector=injector, telemetry=telemetry)
        experiment_results: List[ExperimentResult] = []

        # Run up to 3 planned experiments
        active_experiments = chaos_plan.experiments[:3]

        for i, exp in enumerate(active_experiments, 1):
            logger.info(f"\n--- [Experiment {i}/{len(active_experiments)}] {exp.id}: {exp.name} ---")

            result = guard.execute_safeguarded_experiment(
                experiment_id=exp.id,
                target_service=exp.target_service,
                experiment_type=exp.experiment_type,
                duration_sec=float(exp.duration_sec),
                max_error_rate=float(exp.max_error_rate),
                max_p95_ms=float(exp.max_p95_ms),
            )
            experiment_results.append(result)

            status_str = "🚨 KILL-SWITCH TRIGGERED" if result.kill_switch_triggered else "🛡️ COMPLETED SAFELY"
            logger.info(
                f"Result: {status_str} | MTTR: {result.mttr_sec:.2f}s | "
                f"Peak Error: {result.failure_metrics.get('error_rate', 0)*100:.1f}% | "
                f"Peak p95: {result.failure_metrics.get('p95_latency_ms', 0):.1f}ms"
            )

            # Brief cooling period to ensure system stabilizes before next test
            if i < len(active_experiments):
                logger.info("Cooling buffer (3s) to allow pipeline normalization...")
                time.sleep(3.0)

        # -------------------------------------------------------------
        # STAGE 6: Post-Mortem Analysis & Gemini Resilience Audit
        # -------------------------------------------------------------
        logger.info("\n>>> STAGE 6: Generating AI Post-Mortem Resilience Report & Actionable Fixes...")
        reporter = AIReporter()
        report = reporter.generate_report(
            results=experiment_results,
            baseline_stats=baseline_dict,
            topology=topology,
        )

        # Save all telemetry history
        telemetry.save_history(filepath=str(TELEMETRY_LOG_FILE))

        # -------------------------------------------------------------
        # STAGE 7: Executive Summary & Next Steps
        # -------------------------------------------------------------
        print("\n" + "=" * 80)
        print("                 🏁  CHAOS AUDIT EXECUTION COMPLETE  🏁")
        print("=" * 80)
        print(f"\n📊 Overall Resilience Score: {report.overall_resilience_score} / 100")
        print(f"\n📝 Executive Summary:\n{report.summary}\n")

        print("🔍 Detected Vulnerabilities:")
        for v in report.vulnerabilities:
            print(f"  • [{v.severity}] {v.title} ({v.service}): {v.description}")

        print("\n🛠️ Prescribed Cloud-Native Remediations:")
        for f in sorted(report.prescribed_fixes, key=lambda x: x.priority):
            print(f"  • P{f.priority} [{f.service}] {f.fix_type}: {f.recommendation}")

        print("\n📁 Generated Artifacts:")
        print(f"  1. JSON Report:       {REPORT_JSON_FILE}")
        print(f"  2. Markdown Report:   {REPORT_MD_FILE}")
        print(f"  3. Topology Map:      {discovery.primary_url} -> discovered_topology.json")
        print(f"  4. Telemetry Stream:  {TELEMETRY_LOG_FILE}")
        print(f"  5. Plan Cache:        {CACHE_PLAN_FILE}")
        print("\n🌐 Next Step: Launch the live Streamlit dashboard by running:")
        print("   .venv/bin/streamlit run dashboard.py\n")

    finally:
        # Guarantee traffic worker shutdown and failsafe unpause
        logger.info("Ensuring all background workers stop and containers remain healthy...")
        telemetry.stop()
        injector.emergency_rollback_all()


if __name__ == "__main__":
    run_pipeline()
