"""Stage 2: Gemini Flash AI Chaos Planner with Structured Outputs, Local Cache & Offline Fallback."""

import json
import logging
import os
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from config import (
    ALLOWED_TARGET_SERVICES,
    CACHE_PLAN_FILE,
    DEFAULT_MAX_ERROR_RATE,
    DEFAULT_MAX_P95_MS,
    GEMINI_API_KEY,
    GEMINI_MODEL,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AIPlanner")


class ChaosExperiment(BaseModel):
    id: str = Field(description="Unique experiment ID (e.g., EXP-001)")
    name: str = Field(description="Descriptive experiment title")
    target_service: str = Field(description="Docker container or service name to inject failure into")
    experiment_type: Literal["container_pause", "cpu_throttle", "network_latency"] = Field(
        description="Type of failure injection"
    )
    duration_sec: int = Field(default=8, description="Target duration of failure injection in seconds")
    max_error_rate: float = Field(default=DEFAULT_MAX_ERROR_RATE, description="Tolerated 5xx error rate (0.0 - 1.0)")
    max_p95_ms: float = Field(default=DEFAULT_MAX_P95_MS, description="Tolerated p95 latency in ms before kill-switch")
    hypothesis: str = Field(description="Scientific hypothesis on expected system behavior")
    rationale: str = Field(description="Architectural rationale based on dependency topology")
    priority: int = Field(default=1, description="Execution priority (1 = highest)")


class ChaosPlan(BaseModel):
    plan_name: str = Field(description="Name of the chaos engineering campaign")
    architecture_summary: str = Field(description="AI analysis of the discovered architecture and dependencies")
    experiments: List[ChaosExperiment] = Field(
        min_length=3, description="List of at least 3 prioritized chaos experiments"
    )


def generate_fallback_plan(topology: Dict[str, Any]) -> ChaosPlan:
    """Generates an intelligent topology-aware fallback plan when Gemini API is offline or unauthenticated."""
    logger.info("Generating expert fallback chaos plan based on discovered topology...")

    discovered_names = [n.get("name") for n in topology.get("nodes", [])]
    target_cart = "cart" if "cart" in discovered_names else "cartservice"
    target_catalog = "product-catalog" if "product-catalog" in discovered_names else "productcatalogservice"
    target_rec = "recommendation" if "recommendation" in discovered_names else "recommendationservice"

    return ChaosPlan(
        plan_name="Cloud-Native Resilience & Cascade Prevention Audit",
        architecture_summary=(
            f"Evaluated {topology.get('node_count', 0)} microservices and {topology.get('edge_count', 0)} "
            "inter-service call paths. Frontend proxies traffic into core domain services: cart, catalog, and checkout. "
            "Primary systemic risk identified in single-point-of-failure cascade between frontend and stateful services."
        ),
        experiments=[
            ChaosExperiment(
                id="EXP-001",
                name="Cart Service Total Outage Simulation",
                target_service=target_cart,
                experiment_type="container_pause",
                duration_sec=8,
                max_error_rate=0.30,
                max_p95_ms=1200.0,
                hypothesis="Pausing cart will trigger 500 errors in user add-to-cart operations unless fallback in-memory or degraded cart mode exists.",
                rationale="Cart is directly downstream of frontend proxy; high caller volume makes it critical for shopping workflow.",
                priority=1
            ),
            ChaosExperiment(
                id="EXP-002",
                name="Product Catalog CPU Starvation & Lock Contention",
                target_service=target_catalog,
                experiment_type="cpu_throttle",
                duration_sec=8,
                max_error_rate=0.25,
                max_p95_ms=1500.0,
                hypothesis="Throttling CPU to 10% on catalog service will cause p95 latency spikes on homepage rendering; connection pool exhaustion may occur.",
                rationale="Product catalog serves all product detail queries. Slowness directly degrades storefront p95 latency.",
                priority=2
            ),
            ChaosExperiment(
                id="EXP-003",
                name="Recommendation Engine Degradation & Netem Delay",
                target_service=target_rec,
                experiment_type="network_latency",
                duration_sec=8,
                max_error_rate=0.20,
                max_p95_ms=1200.0,
                hypothesis="Recommendation slowness should be masked gracefully by timeout or empty recommendation fallback without impacting purchase checkout.",
                rationale="Non-critical dependency; tests whether circuit breaker or graceful degradation pattern is correctly implemented.",
                priority=3
            ),
        ]
    )


class AIChaosPlanner:
    """Produces structured chaos engineering plans using Gemini 2.5 Flash with fallback protection."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.model = GEMINI_MODEL

    def create_plan(self, topology: Dict[str, Any], force_refresh: bool = False) -> ChaosPlan:
        """Generates or loads cached ChaosPlan."""
        # Check local cache first if not force_refresh
        if not force_refresh and CACHE_PLAN_FILE.exists():
            try:
                with open(CACHE_PLAN_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                plan = ChaosPlan.model_validate(data)
                logger.info(f"Loaded existing ChaosPlan from cache: {CACHE_PLAN_FILE}")
                return plan
            except Exception as e:
                logger.warning(f"Could not load cached chaos plan ({e}); generating new plan...")

        # If Gemini API Key is available, invoke Gemini 2.5 Flash
        if self.api_key:
            try:
                logger.info(f"Invoking Google GenAI ({self.model}) for structured ChaosPlan generation...")
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.api_key)

                prompt = (
                    "You are a Principal Cloud-Native Reliability Engineer designing a chaos test suite for the "
                    "OpenTelemetry Demo microservices running locally in Docker.\n\n"
                    f"Discovered Topology:\n{json.dumps(topology, indent=2)}\n\n"
                    f"Allowed Target Services (do NOT target proxies or collectors):\n{json.dumps(ALLOWED_TARGET_SERVICES)}\n\n"
                    "Requirements:\n"
                    "1. Propose at least 3 prioritized, rigorous chaos experiments testing resilience.\n"
                    "2. Allowed experiment types: 'container_pause', 'cpu_throttle', 'network_latency'.\n"
                    "3. Define realistic safety guard thresholds (max_error_rate around 0.20-0.30, max_p95_ms around 1000-1500ms).\n"
                    "4. Include scientific hypotheses and architectural rationales based on graph dependencies."
                )

                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ChaosPlan,
                        temperature=0.2,
                    ),
                )

                if response.text:
                    plan = ChaosPlan.model_validate_json(response.text)
                    self._save_cache(plan)
                    logger.info("Successfully received structured ChaosPlan from Gemini.")
                    return plan

            except Exception as e:
                logger.warning(f"Gemini API generation encountered an issue ({e}). Activating resilience fallback.")

        # Fallback to local expert plan generator
        fallback_plan = generate_fallback_plan(topology)
        self._save_cache(fallback_plan)
        return fallback_plan

    def _save_cache(self, plan: ChaosPlan) -> None:
        """Caches generated plan to disk."""
        try:
            with open(CACHE_PLAN_FILE, "w", encoding="utf-8") as f:
                f.write(plan.model_dump_json(indent=2))
            logger.info(f"ChaosPlan cached to: {CACHE_PLAN_FILE}")
        except Exception as e:
            logger.warning(f"Could not write cache file: {e}")


if __name__ == "__main__":
    from topology import TopologyDiscovery
    topo = TopologyDiscovery().discover()
    planner = AIChaosPlanner()
    plan = planner.create_plan(topo, force_refresh=True)
    print("\n--- AI Chaos Plan ---")
    print(f"Plan: {plan.plan_name}")
    print(f"Experiments ({len(plan.experiments)}):")
    for exp in plan.experiments:
        print(f"  [{exp.id}] {exp.name} -> {exp.target_service} ({exp.experiment_type})")
