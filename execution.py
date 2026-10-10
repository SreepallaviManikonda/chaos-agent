"""Shared execution ownership and measured dashboard artifacts."""
import fcntl
import json
import signal
import threading
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from config import BASE_DIR

@contextmanager
def campaign_scope(injector):
    # Cross-process lock prevents CLI and dashboard sessions from overlapping faults.
    with open(BASE_DIR / '.campaign.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another chaos campaign is already running')
        previous = {}
        def interrupted(signum, frame):
            raise KeyboardInterrupt(f'Signal {signum}')
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGINT, signal.SIGTERM):
                previous[sig] = signal.signal(sig, interrupted)
        try:
            yield
        finally:
            try:
                if not injector.emergency_rollback_all():
                    raise RuntimeError('Cleanup failed; inspect the owned experiment resources')
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
                fcntl.flock(lock, fcntl.LOCK_UN)

def save_dashboard_results(results, baseline, report, path=None):
    data = {'schema_version': 2, 'provenance': 'measured',
            'score': report.overall_resilience_score, 'baseline': baseline, 'experiments': []}
    for r in results:
        data['experiments'].append({
            'id': r.experiment_id, 'target': r.target_service, 'fault': r.experiment_type,
            'duration': r.actual_duration_sec, 'peak_p95': r.failure_metrics.get('p95_latency_ms', 0),
            'peak_error_rate': r.failure_metrics.get('error_rate', 0) * 100,
            'mttr': r.mttr_sec if r.recovery_confirmed else None,
            'kill_switch_triggered': r.kill_switch_triggered, 'status': r.status,
            'rollback_sec': r.rollback_sec, 'timeline': [], 'raw': asdict(r)})
    dest = Path(path or BASE_DIR / 'results.json')
    tmp = dest.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(dest)

def run_single(target, fault, error_threshold, latency_threshold, results_path=None):
    from chaos_injector import ChaosInjector
    from telemetry import TelemetryCollector
    from safety_guard import SafetyGuard
    from ai_reporter import AIReporter
    injector = ChaosInjector()
    if not injector.client:
        raise RuntimeError('Docker unavailable')
    with campaign_scope(injector):
        telemetry = TelemetryCollector()
        telemetry.start()
        try:
            baseline = asdict(telemetry.capture_baseline(5))
            result = SafetyGuard(injector, telemetry).execute_safeguarded_experiment(
                'EXP-LIVE', target, fault, max_error_rate=error_threshold, max_p95_ms=latency_threshold)
            report = AIReporter().generate_report([result], baseline)
            save_dashboard_results([result], baseline, report, results_path)
            return result
        finally:
            telemetry.stop()
            telemetry.save_history()
