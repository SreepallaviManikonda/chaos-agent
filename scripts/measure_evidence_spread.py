#!/usr/bin/env python3
"""Run multi-trial cart experiment spread and no-fault control run to strengthen empirical evidence."""

import json
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path

from chaos_injector import ChaosInjector
from config import BASE_DIR, FRONTEND_URL
from safety_guard import SafetyGuard
from telemetry import TelemetryCollector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("EvidenceBench")

def run_control_and_spread():
    injector = ChaosInjector()
    if not injector.client:
        logger.error("Docker daemon unavailable.")
        sys.exit(1)

    telemetry = TelemetryCollector(target_url=FRONTEND_URL, rate_rps=10)
    telemetry.start()
    guard = SafetyGuard(injector=injector, telemetry=telemetry)

    try:
        # 1. No-fault control run (10 seconds of baseline steady state)
        logger.info(">>> Running 10-second No-Fault Control Run (Baseline noise measurement)...")
        time.sleep(3.0)
        control_stats = telemetry.capture_baseline(duration_sec=7.0)
        control_data = {
            "trial": "CONTROL_NO_FAULT",
            "duration_sec": 7.0,
            "p50_ms": control_stats.p50_latency_ms,
            "p95_ms": control_stats.p95_latency_ms,
            "avg_ms": control_stats.avg_latency_ms,
            "error_rate": control_stats.error_rate,
            "kill_switch_triggered": False,
            "notes": "Healthy steady state; no faults injected"
        }
        logger.info(f"Control Run: p50={control_data['p50_ms']:.1f}ms, p95={control_data['p95_ms']:.1f}ms, errors={control_data['error_rate']*100:.1f}%")

        # 2. Multi-trial Cart Experiment Spread (3 trials)
        cart_trials = []
        for trial_num in range(1, 4):
            logger.info(f"\n>>> Running Cart Outage Trial {trial_num}/3...")
            time.sleep(3.0) # Cooling buffer
            res = guard.execute_safeguarded_experiment(
                experiment_id=f"EXP-CART-T{trial_num}",
                target_service="cart",
                experiment_type="container_pause",
                duration_sec=8.0,
                max_error_rate=0.30,
                max_p95_ms=1500.0
            )
            trial_summary = {
                "trial": trial_num,
                "mttr_sec": res.mttr_sec,
                "rollback_sec": res.rollback_sec,
                "peak_p95_ms": res.failure_metrics.get("p95_latency_ms", 0),
                "peak_error_rate": res.failure_metrics.get("error_rate", 0) * 100,
                "kill_switch_triggered": res.kill_switch_triggered,
                "status": res.status
            }
            cart_trials.append(trial_summary)
            logger.info(f"Trial {trial_num} Result: MTTR={res.mttr_sec:.2f}s, rollback={res.rollback_sec*1000:.1f}ms, peak_p95={trial_summary['peak_p95_ms']:.1f}ms")

        # Calculate statistics
        mttrs = [t["mttr_sec"] for t in cart_trials]
        rollbacks = [t["rollback_sec"] for t in cart_trials]
        mean_mttr = sum(mttrs) / len(mttrs)
        mttr_spread = max(mttrs) - min(mttrs)
        mean_rollback = (sum(rollbacks) / len(rollbacks)) * 1000

        evidence_payload = {
            "control_run": control_data,
            "cart_multi_run": {
                "trials": cart_trials,
                "mean_mttr_sec": round(mean_mttr, 2),
                "mttr_min_sec": min(mttrs),
                "mttr_max_sec": max(mttrs),
                "mttr_spread_sec": round(mttr_spread, 2),
                "mean_rollback_ms": round(mean_rollback, 2)
            }
        }

        out_file = BASE_DIR / "evidence_benchmark.json"
        out_file.write_text(json.dumps(evidence_payload, indent=2))
        logger.info(f"\n✅ Evidence Benchmark saved to {out_file}")
        logger.info(f"Summary: MTTR Spread = {mean_mttr:.2f}s (range: {min(mttrs):.2f}s - {max(mttrs):.2f}s, spread: ±{mttr_spread/2:.2f}s), Mean Revert: {mean_rollback:.1f}ms")

    finally:
        telemetry.stop()

if __name__ == "__main__":
    run_control_and_spread()
