"""Stage 2 & 4: Continuous Traffic Generation, Real-Time Observability & MTTR Measurement."""

import json
from concurrent.futures import ThreadPoolExecutor
import logging
import math
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

import httpx

from config import (
    DEFAULT_MAX_P95_MS,
    FRONTEND_URL,
    PROBE_RATE_RPS,
    PROBE_TIMEOUT_SEC,
    TELEMETRY_LOG_FILE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Telemetry")


@dataclass
class ProbeSample:
    timestamp: float
    iso_time: str
    status_code: int
    latency_ms: float
    is_error: bool
    event_tag: Optional[str] = None


@dataclass
class RollingStats:
    timestamp: float
    window_sec: float
    total_requests: int
    error_count: int
    error_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    avg_latency_ms: float
    healthy: bool
    latest_sample_timestamp: float = 0.0


class TelemetryCollector:
    """Asynchronous background load generator and real-time observability engine."""

    def __init__(self, target_url: str = FRONTEND_URL, rate_rps: int = PROBE_RATE_RPS):
        self.target_url = target_url
        self.rate_rps = rate_rps
        self.interval_sec = 1.0 / max(1, rate_rps)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Rolling buffer of recent probes (stores up to last 2000 probes)
        self._samples: Deque[ProbeSample] = deque(maxlen=2000)
        # Full session history for reporting and dashboard
        self._full_history: List[Dict[str, Any]] = []

        # User journey paths exercising core microservices
        self.probe_paths = ["/", "/api/products", "/api/cart", "/api/recommendations"]
        self._path_idx = 0

        self._current_event_tag: Optional[str] = None

    def tag_event(self, tag: Optional[str]) -> None:
        """Tags subsequent probes with an incident/experiment identifier."""
        with self._lock:
            self._current_event_tag = tag

    def start(self) -> None:
        """Starts background traffic generation and metric polling."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="TelemetryWorker")
        self._thread.start()
        logger.info(f"Telemetry load generator started against {self.target_url} at {self.rate_rps} req/sec.")

    def stop(self) -> None:
        """Stops background traffic generation."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
        logger.info("Telemetry load generator stopped.")

    def _worker_loop(self) -> None:
        # Bounded concurrency sustains the configured arrival rate during slow requests.
        workers = max(4, int(self.rate_rps * PROBE_TIMEOUT_SEC * 2))
        pending = set()
        with httpx.Client(timeout=PROBE_TIMEOUT_SEC) as client, ThreadPoolExecutor(max_workers=workers) as pool:
            while self._running:
                pending = {f for f in pending if not f.done()}
                if len(pending) < workers:
                    with self._lock:
                        path = self.probe_paths[self._path_idx % len(self.probe_paths)]
                        self._path_idx += 1
                        tag = self._current_event_tag
                    pending.add(pool.submit(self._probe, client, path, tag))
                time.sleep(self.interval_sec)

    def _probe(self, client, path, tag):
        started = time.perf_counter()
        try:
            response = client.get(f"{self.target_url.rstrip('/')}{path}")
            status = response.status_code
        except httpx.TimeoutException:
            status = 504
        except Exception:
            status = 502
        completed = time.time()
        sample = ProbeSample(
            timestamp=completed,
            iso_time=datetime.fromtimestamp(completed, timezone.utc).isoformat(),
            status_code=status,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            is_error=not 200 <= status < 400,
            event_tag=tag,
        )
        with self._lock:
            self._samples.append(sample)
            self._full_history.append(asdict(sample))

    def get_stats(self, window_sec: float = 1.0) -> RollingStats:
        """Calculates rolling statistics over the requested window (default 1.0s)."""
        now = time.time()
        cutoff = now - max(0.5, window_sec)

        with self._lock:
            # Filter samples within window
            recent = [s for s in self._samples if s.timestamp >= cutoff]

        if not recent:
            return RollingStats(
                timestamp=now,
                window_sec=window_sec,
                total_requests=0,
                error_count=0,
                error_rate=0.0,
                p50_latency_ms=0.0,
                p95_latency_ms=0.0,
                avg_latency_ms=0.0,
                healthy=False
            )

        total = len(recent)
        errors = sum(1 for s in recent if s.is_error)
        error_rate = round(errors / total, 4)

        latencies = sorted(s.latency_ms for s in recent)
        p50_idx = int(len(latencies) * 0.50)
        p95_idx = min(int(math.ceil(len(latencies) * 0.95)) - 1, len(latencies) - 1)
        p50 = round(latencies[p50_idx], 2)
        p95 = round(latencies[max(0, p95_idx)], 2)
        avg = round(sum(latencies) / len(latencies), 2)

        is_healthy = (error_rate == 0.0) and (p95 < DEFAULT_MAX_P95_MS)

        return RollingStats(
            timestamp=now,
            window_sec=window_sec,
            total_requests=total,
            error_count=errors,
            error_rate=error_rate,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            avg_latency_ms=avg,
            latest_sample_timestamp=max(s.timestamp for s in recent),
            healthy=is_healthy
        )

    def measure_mttr(
        self,
        timeout_sec: float = 30.0,
        target_error_threshold: float = 0.05,
        target_p95_threshold_ms: float = 1000.0,
        poll_interval_sec: float = 0.5
    ) -> float:
        """Calculates elapsed seconds until error rate drops back to 0.0 and latency normalizes."""
        logger.info(f"Measuring MTTR (timeout: {timeout_sec}s, target error rate <= {target_error_threshold})...")
        t_start = time.time()
        self.last_recovery_confirmed = False
        consecutive_healthy = 0
        required_healthy_checks = 2
        last_seen = t_start

        while (time.time() - t_start) < timeout_sec:
            stats = self.get_stats(window_sec=2.0)
            is_recovered = (stats.latest_sample_timestamp > last_seen) and (stats.total_requests >= 5) and (stats.error_rate <= target_error_threshold) and (stats.p95_latency_ms <= target_p95_threshold_ms)

            if is_recovered:
                last_seen = stats.latest_sample_timestamp
                consecutive_healthy += 1
                if consecutive_healthy >= required_healthy_checks:
                    mttr = round(time.time() - t_start, 2)
                    mttr = max(0.1, mttr)
                    logger.info(f"System recovered! Measured MTTR: {mttr}s (Error rate: {stats.error_rate}, p95: {stats.p95_latency_ms}ms)")
                    self.last_recovery_confirmed = True
                    return mttr
            else:
                consecutive_healthy = 0

            time.sleep(poll_interval_sec)

        elapsed = round(time.time() - t_start, 2)
        logger.warning(f"MTTR measurement timed out after {elapsed}s without full recovery.")
        return elapsed

    def capture_baseline(self, duration_sec: float = 5.0) -> RollingStats:
        """Captures steady-state metrics over duration_sec."""
        logger.info(f"Capturing steady-state baseline metrics over {duration_sec}s...")
        time.sleep(duration_sec)
        baseline = self.get_stats(window_sec=duration_sec)
        logger.info(
            f"Baseline captured: Total={baseline.total_requests}, "
            f"ErrorRate={baseline.error_rate*100:.1f}%, "
            f"p50={baseline.p50_latency_ms}ms, p95={baseline.p95_latency_ms}ms"
        )
        return baseline

    def get_history(self) -> List[Dict[str, Any]]:
        """Returns snapshot of probe history."""
        with self._lock:
            return list(self._full_history)

    def save_history(self, filepath: Optional[str] = None) -> None:
        """Saves telemetry history to JSON for downstream analytics and dashboard."""
        out_path = filepath or TELEMETRY_LOG_FILE
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                with self._lock:
                    json.dump(self._full_history, f, indent=2)
            logger.info(f"Saved {len(self._full_history)} telemetry data points to {out_path}")
        except Exception as e:
            logger.error(f"Failed to save telemetry log: {e}")


if __name__ == "__main__":
    collector = TelemetryCollector()
    collector.start()
    try:
        baseline = collector.capture_baseline(duration_sec=3.0)
        print("\n--- Telemetry Baseline ---")
        print(asdict(baseline))
    finally:
        collector.stop()
