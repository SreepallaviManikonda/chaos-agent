"""Stage 3: Automated Safety Watchdog & Kill-Switch Controller."""

import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from chaos_injector import ChaosInjector
from config import (
    DEFAULT_MAX_ERROR_RATE,
    DEFAULT_MAX_P95_MS,
    WATCHDOG_POLL_INTERVAL_SEC,
)
from telemetry import TelemetryCollector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SafetyGuard")


@dataclass
class ExperimentResult:
    experiment_id: str
    target_service: str
    experiment_type: str
    planned_duration_sec: float
    actual_duration_sec: float
    kill_switch_triggered: bool
    trigger_reason: Optional[str]
    breached_metric: Optional[str]
    breached_value: Optional[float]
    baseline_metrics: Dict[str, Any]
    failure_metrics: Dict[str, Any]
    recovery_metrics: Dict[str, Any]
    mttr_sec: float


class SafetyGuard:
    """Supervises chaos experiments, continuously monitoring health and triggering rollbacks on SLA breaches."""

    def __init__(self, injector: ChaosInjector, telemetry: TelemetryCollector):
        self.injector = injector
        self.telemetry = telemetry

    def execute_safeguarded_experiment(
        self,
        experiment_id: str,
        target_service: str,
        experiment_type: str,
        duration_sec: float = 8.0,
        max_error_rate: float = DEFAULT_MAX_ERROR_RATE,
        max_p95_ms: float = DEFAULT_MAX_P95_MS,
    ) -> ExperimentResult:
        """Runs a chaos experiment with active 500ms safety watchdog monitoring."""
        logger.info(
            f"=== Starting Experiment [{experiment_id}]: {experiment_type} on '{target_service}' "
            f"(Duration: {duration_sec}s, Max Error: {max_error_rate*100:.0f}%, Max p95: {max_p95_ms}ms) ==="
        )

        # 1. Capture pre-injection steady state metrics
        stats_before = self.telemetry.get_stats(window_sec=2.0)
        baseline_metrics = asdict(stats_before)

        # 2. Tag telemetry stream
        self.telemetry.tag_event(f"{experiment_id}_active")

        # 3. Inject chaos
        injected = self.injector.inject(target_service, experiment_type)
        if not injected:
            logger.error(f"Experiment [{experiment_id}] failed during injection. Skipping.")
            self.telemetry.tag_event(None)
            return ExperimentResult(
                experiment_id=experiment_id,
                target_service=target_service,
                experiment_type=experiment_type,
                planned_duration_sec=duration_sec,
                actual_duration_sec=0.0,
                kill_switch_triggered=False,
                trigger_reason="Injection initiation failed",
                breached_metric=None,
                breached_value=None,
                baseline_metrics=baseline_metrics,
                failure_metrics={},
                recovery_metrics={},
                mttr_sec=0.0
            )

        # 4. Supervise with 500ms watchdog loop
        start_time = time.time()
        kill_switch_triggered = False
        trigger_reason: Optional[str] = None
        breached_metric: Optional[str] = None
        breached_value: Optional[float] = None
        failure_samples = []

        logger.info(f"Safety watchdog engaged. Polling health every {WATCHDOG_POLL_INTERVAL_SEC*1000:.0f}ms...")

        while (time.time() - start_time) < duration_sec:
            time.sleep(WATCHDOG_POLL_INTERVAL_SEC)
            current_stats = self.telemetry.get_stats(window_sec=1.0)
            failure_samples.append(asdict(current_stats))

            # Breach Condition 1: Error rate exceeded
            if current_stats.error_rate > max_error_rate:
                kill_switch_triggered = True
                breached_metric = "error_rate"
                breached_value = current_stats.error_rate
                trigger_reason = (
                    f"CRITICAL SLA BREACH: Error rate reached {current_stats.error_rate*100:.1f}% "
                    f"(Threshold: {max_error_rate*100:.1f}%)"
                )
                logger.warning(f"🚨 KILL-SWITCH TRIGGERED: {trigger_reason}")
                break

            # Breach Condition 2: p95 latency exceeded
            if current_stats.p95_latency_ms > max_p95_ms:
                kill_switch_triggered = True
                breached_metric = "p95_latency_ms"
                breached_value = current_stats.p95_latency_ms
                trigger_reason = (
                    f"CRITICAL SLA BREACH: p95 latency reached {current_stats.p95_latency_ms:.1f}ms "
                    f"(Threshold: {max_p95_ms:.1f}ms)"
                )
                logger.warning(f"🚨 KILL-SWITCH TRIGGERED: {trigger_reason}")
                break

        actual_duration = round(time.time() - start_time, 2)

        # 5. Rollback failure immediately
        logger.info(f"Executing rollback for [{experiment_id}] on '{target_service}'...")
        if kill_switch_triggered:
            # Immediate emergency rollback
            self.injector.revert(target_service)
            self.injector.emergency_rollback_all()
            logger.info("🛡️ Automated safety kill-switch successfully reverted injection and averted system failure!")
        else:
            self.injector.revert(target_service)
            logger.info(f"Experiment [{experiment_id}] completed full duration ({actual_duration}s) safely.")

        self.telemetry.tag_event(f"{experiment_id}_recovery")

        # 6. Measure MTTR (Mean Time To Recover)
        peak_stats = failure_samples[-1] if failure_samples else baseline_metrics
        mttr = self.telemetry.measure_mttr(
            timeout_sec=20.0,
            target_error_threshold=0.05,
            target_p95_threshold_ms=max(baseline_metrics.get("p95_latency_ms", 500.0) * 1.5, 800.0)
        )

        recovery_stats = asdict(self.telemetry.get_stats(window_sec=2.0))
        self.telemetry.tag_event(None)

        return ExperimentResult(
            experiment_id=experiment_id,
            target_service=target_service,
            experiment_type=experiment_type,
            planned_duration_sec=duration_sec,
            actual_duration_sec=actual_duration,
            kill_switch_triggered=kill_switch_triggered,
            trigger_reason=trigger_reason,
            breached_metric=breached_metric,
            breached_value=breached_value,
            baseline_metrics=baseline_metrics,
            failure_metrics=peak_stats,
            recovery_metrics=recovery_stats,
            mttr_sec=mttr
        )
