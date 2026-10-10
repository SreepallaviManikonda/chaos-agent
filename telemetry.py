"""Stage 2 & 4: Continuous Traffic Generation, Real-Time Observability & MTTR Measurement."""

import json
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
            self._thread.join(timeout=3.0)
        logger.info("Telemetry load generator stopped.")

    def _worker_loop(self) -> None:
        """Continuous probing loop executing at targeted RPS."""
        transport = httpx.HTTPTransport(retries=0)
        client = httpx.Client(timeout=PROBE_TIMEOUT_SEC, transport=transport)

        while self._running:
            t0 = time.perf_counter()
            now_ts = time.time()
            iso_str = datetime.now(timezone.utc).isoformat()
            tag = self._current_event_tag

            status_code = 0
            is_error = False
            latency_ms = 0.0

            with self._lock:
                req_path = self.probe_paths[self._path_idx % len(self.probe_paths)]
                self._path_idx += 1
            probe_target = f"{self.target_url.rstrip('/')}{req_path}"

            try:
                resp = client.get(probe_target)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                status_code = resp.status_code
                if status_code >= 500 or status_code == 0:
                    is_error = True
            except httpx.TimeoutException:
                latency_ms = PROBE_TIMEOUT_SEC * 1000.0
                status_code = 504
                is_error = True
            except Exception:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                status_code = 502
                is_error = True

            sample = ProbeSample(
                timestamp=now_ts,
                iso_time=iso_str,
                status_code=status_code,
                latency_ms=round(latency_ms, 2),
                is_error=is_error,
                event_tag=tag
            )

            with self._lock:
                self._samples.append(sample)
                self._full_history.append(asdict(sample))

            elapsed = time.perf_counter() - t0
            sleep_time = max(0.0, self.interval_sec - elapsed)
            time.sleep(sleep_time)

        client.close()

    def get_stats(self, window_sec: float = 1.0) -> RollingStats:
        """Calculates rolling statistics over the requested window (default 1.0s)."""
        now = time.time()
        cutoff = now - max(0.5, window_sec)

        with self._lock:
            # Filter samples within window
            recent = [s for s in self._samples if s.timestamp >= cutoff]
            if not recent and self._samples:
                # If window is very tight, take the last 10 samples
                recent = list(self._samples)[-10:]

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
                healthy=True
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
        consecutive_healthy = 0
        required_healthy_checks = 2

        while (time.time() - t_start) < timeout_sec:
            stats = self.get_stats(window_sec=2.0)
            is_recovered = (stats.error_rate <= target_error_threshold) and (stats.p95_latency_ms <= target_p95_threshold_ms)

            if is_recovered:
                consecutive_healthy += 1
                if consecutive_healthy >= required_healthy_checks:
                    mttr = round(time.time() - t_start - (consecutive_healthy - 1) * poll_interval_sec, 2)
                    mttr = max(0.1, mttr)
                    logger.info(f"System recovered! Measured MTTR: {mttr}s (Error rate: {stats.error_rate}, p95: {stats.p95_latency_ms}ms)")
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
