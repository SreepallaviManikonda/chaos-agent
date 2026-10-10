"""Global configuration and thresholds for the Chaos Engineering Agent."""

import os
from pathlib import Path
from typing import List

# Base directory of the chaos agent
BASE_DIR = Path(__file__).resolve().parent

# Target Application Endpoints
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080")
JAEGER_PRIMARY_URL = os.getenv("JAEGER_PRIMARY_URL", "http://localhost:8080/jaeger/ui/api/dependencies")
JAEGER_FALLBACK_URL = os.getenv("JAEGER_FALLBACK_URL", "http://localhost:16686/api/dependencies")
PROMETHEUS_PRIMARY_URL = os.getenv("PROMETHEUS_PRIMARY_URL", "http://localhost:9090/api/v1/query")
PROMETHEUS_FALLBACK_URL = os.getenv("PROMETHEUS_FALLBACK_URL", "http://localhost:8080/prometheus/api/v1/query")

# Potential locations for the OpenTelemetry Demo compose file
COMPOSE_FILE_CANDIDATES: List[Path] = [
    Path("/Users/sreepallavimanikonda/opentelemetry-demo/compose.yaml"),
    BASE_DIR.parent / "opentelemetry-demo" / "compose.yaml",
    BASE_DIR / "compose.yaml",
]

# Safety Guard & Kill-Switch Thresholds
DEFAULT_MAX_ERROR_RATE: float = 0.30        # 30% HTTP 5xx error rate
DEFAULT_MAX_P95_MS: float = 1500.0          # 1500ms p95 latency
WATCHDOG_POLL_INTERVAL_SEC: float = 0.5     # Watchdog poll every 500ms

# Probing Traffic Settings
PROBE_RATE_RPS: int = 10                    # 10 requests / second
PROBE_TIMEOUT_SEC: float = 2.5              # Per-probe HTTP timeout
ROLLING_WINDOW_SEC: float = 5.0             # Rolling window for metrics calculation

# AI Model Configuration
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Output Artifact Paths
CACHE_PLAN_FILE = BASE_DIR / "cache_chaos_plan.json"
REPORT_JSON_FILE = BASE_DIR / "findings_report.json"
REPORT_MD_FILE = BASE_DIR / "FINDINGS_REPORT.md"
TELEMETRY_LOG_FILE = BASE_DIR / "telemetry_history.json"
TOPOLOGY_FILE = BASE_DIR / "discovered_topology.json"

# Safe Chaos Injection Targets (services that can be safely targeted without destroying proxy/infra)
ALLOWED_TARGET_SERVICES = [
    "cart",
    "product-catalog",
    "recommendation",
    "payment",
    "shipping",
    "quote",
    "email",
    "currency",
    "ad"
]

# Critical Infrastructure Containers (Do NOT pause or throttle these)
PROTECTED_CONTAINERS = [
    "frontend-proxy",
    "otel-collector",
    "jaeger",
    "prometheus",
    "grafana",
    "opensearch",
    "load-generator"
]
