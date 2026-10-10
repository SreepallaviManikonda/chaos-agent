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
    status: str = "completed"
    rollback_sec: Optional[float] = None
    recovery_confirmed: bool = False


class SafetyGuard:
    """Synchronous supervisor; telemetry runs concurrently in background workers."""
    def __init__(self, injector, telemetry):
        self.injector, self.telemetry = injector, telemetry

    def execute_safeguarded_experiment(self, experiment_id, target_service, experiment_type,
                                     duration_sec=8.0, max_error_rate=DEFAULT_MAX_ERROR_RATE,
                                     max_p95_ms=DEFAULT_MAX_P95_MS):
        if not 0 < duration_sec <= 60 or not 0 < max_error_rate <= .5 or not 0 < max_p95_ms <= 3000:
            raise ValueError('Invalid experiment duration or safety thresholds')
        baseline = asdict(self.telemetry.get_stats(window_sec=2.0))
        result = ExperimentResult(experiment_id, target_service, experiment_type, duration_sec,
                                  0, False, None, None, None, baseline, {}, {}, 0,
                                  status='not_run')
        if baseline['total_requests'] < 5 or baseline['error_rate'] > .05 or baseline['p95_latency_ms'] > max_p95_ms:
            result.trigger_reason = 'Insufficient or unhealthy baseline; no fault injected'
            return result
        self.telemetry.tag_event(f'{experiment_id}_active')
        started = time.monotonic()
        samples = []
        try:
            if not self.injector.inject(target_service, experiment_type):
                result.status = 'injection_failed'
                result.trigger_reason = 'Fault could not be applied'
                return result
            started = time.monotonic()
            result.status = 'completed'
            while time.monotonic() - started < duration_sec:
                time.sleep(WATCHDOG_POLL_INTERVAL_SEC)
                stats = asdict(self.telemetry.get_stats(window_sec=1.0))
                samples.append(stats)
                metric = None
                if stats['total_requests'] == 0:
                    metric = 'total_requests'
                elif stats['error_rate'] > max_error_rate:
                    metric = 'error_rate'
                elif stats['p95_latency_ms'] > max_p95_ms:
                    metric = 'p95_latency_ms'
                if metric:
                    result.kill_switch_triggered = True
                    result.breached_metric, result.breached_value = metric, stats[metric]
                    result.trigger_reason = f'Safety threshold breached: {metric}={stats[metric]}'
                    result.status = 'aborted'
                    break
            result.actual_duration_sec = round(time.monotonic() - started, 3)
            if samples:
                result.failure_metrics = dict(samples[-1])
                for key in ['error_rate', 'p95_latency_ms', 'p50_latency_ms', 'avg_latency_ms']:
                    result.failure_metrics[key] = max(row[key] for row in samples)
        finally:
            rollback_start = time.monotonic()
            reverted = self.injector.revert(target_service)
            result.rollback_sec = round(time.monotonic() - rollback_start, 4)
            self.telemetry.tag_event(None)
            if not reverted:
                result.status = 'rollback_failed'
                raise RuntimeError(f'Rollback failed for {target_service}; retained for cleanup retry')
        self.telemetry.tag_event(f'{experiment_id}_recovery')
        try:
            result.mttr_sec = self.telemetry.measure_mttr(
                timeout_sec=20, target_error_threshold=.05,
                target_p95_threshold_ms=max(baseline['p95_latency_ms'] * 1.5, 800))
            result.recovery_confirmed = self.telemetry.last_recovery_confirmed
            result.recovery_metrics = asdict(self.telemetry.get_stats(window_sec=2))
            if not result.recovery_confirmed:
                result.status = 'recovery_timeout'
        finally:
            self.telemetry.tag_event(None)
        return result
