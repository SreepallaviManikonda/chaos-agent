"""Stage 1: Topology and Dependency Discovery via Jaeger API & Compose Fallback."""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import httpx
import yaml

from config import (
    COMPOSE_FILE_CANDIDATES,
    JAEGER_FALLBACK_URL,
    JAEGER_PRIMARY_URL,
    TOPOLOGY_FILE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TopologyDiscovery")


class TopologyDiscovery:
    """Discovers and normalizes service topology and call dependencies."""

    def __init__(self, primary_url: str = JAEGER_PRIMARY_URL, fallback_url: str = JAEGER_FALLBACK_URL):
        self.primary_url = primary_url
        self.fallback_url = fallback_url

    def fetch_jaeger_dependencies(self, timeout_sec: float = 4.0) -> Optional[List[Dict[str, Any]]]:
        """Queries Jaeger dependency endpoint for service call graphs."""
        end_ts = int(time.time() * 1000)
        # Lookback 1 hour (3600000 ms) or up to 24 hours
        params = {"endTs": end_ts, "lookback": 3600000}

        for url in [self.primary_url, self.fallback_url]:
            try:
                logger.info(f"Probing Jaeger dependencies at: {url}")
                with httpx.Client(timeout=timeout_sec) as client:
                    resp = client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        deps = data.get("data", [])
                        if deps:
                            logger.info(f"Successfully retrieved {len(deps)} dependency edges from Jaeger ({url})")
                            return deps
                        else:
                            logger.warning(f"Jaeger returned empty dependency data at {url}")
            except Exception as e:
                logger.warning(f"Failed to query Jaeger at {url}: {e}")

        return None

    def parse_compose_file(self) -> Optional[Dict[str, Any]]:
        """Fallback: Parses docker-compose file to build static service dependency graph."""
        target_path: Optional[Path] = None
        for candidate in COMPOSE_FILE_CANDIDATES:
            if candidate.exists() and candidate.is_file():
                target_path = candidate
                break

        if not target_path:
            logger.warning("No docker-compose.yaml file found among candidate paths.")
            return None

        logger.info(f"Parsing static architecture topology from: {target_path}")
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                compose_data = yaml.safe_load(f)

            services = compose_data.get("services", {})
            nodes: Set[str] = set(services.keys())
            edges: List[Dict[str, Any]] = []

            for svc_name, svc_conf in services.items():
                if not isinstance(svc_conf, dict):
                    continue
                # 1. depends_on relationships
                depends_on = svc_conf.get("depends_on", {})
                deps_list = []
                if isinstance(depends_on, list):
                    deps_list = depends_on
                elif isinstance(depends_on, dict):
                    deps_list = list(depends_on.keys())

                for dep in deps_list:
                    edges.append({
                        "caller": svc_name,
                        "callee": dep,
                        "call_count": 50,  # estimated static weight
                        "source": "compose_depends_on"
                    })

                # 2. environment variables matching other services
                env = svc_conf.get("environment", {})
                env_vals = []
                if isinstance(env, dict):
                    env_vals = [str(v) for v in env.values()]
                elif isinstance(env, list):
                    env_vals = [str(v) for v in env]

                for other_svc in nodes:
                    if other_svc != svc_name and any(other_svc in val for val in env_vals):
                        # Avoid duplicates
                        if not any(e["caller"] == svc_name and e["callee"] == other_svc for e in edges):
                            edges.append({
                                "caller": svc_name,
                                "callee": other_svc,
                                "call_count": 25,
                                "source": "compose_env_ref"
                            })

            return {"nodes": sorted(list(nodes)), "edges": edges, "source": f"compose_file ({target_path.name})"}

        except Exception as e:
            logger.error(f"Error parsing compose file: {e}")
            return None

    def discover(self) -> Dict[str, Any]:
        """Discovers topology using Jaeger with automatic Compose fallback."""
        jaeger_data = self.fetch_jaeger_dependencies()
        edges: List[Dict[str, Any]] = []
        nodes_set: Set[str] = set()
        source = "jaeger_api"

        if jaeger_data:
            for item in jaeger_data:
                caller = item.get("parent") or item.get("caller") or ""
                callee = item.get("child") or item.get("callee") or ""
                call_count = int(item.get("callCount") or item.get("call_count") or 1)
                if caller and callee:
                    nodes_set.add(caller)
                    nodes_set.add(callee)
                    edges.append({
                        "caller": caller,
                        "callee": callee,
                        "call_count": call_count
                    })
        else:
            logger.info("Jaeger dependencies unavailable; falling back to compose file.")
            compose_topo = self.parse_compose_file()
            if compose_topo:
                source = compose_topo["source"]
                edges = compose_topo["edges"]
                nodes_set = set(compose_topo["nodes"])
            else:
                # Emergency hardcoded baseline for standard OpenTelemetry Demo
                source = "hardcoded_baseline"
                nodes_set = {"frontend", "cart", "product-catalog", "recommendation", "payment", "shipping", "checkout"}
                edges = [
                    {"caller": "frontend", "callee": "cart", "call_count": 500},
                    {"caller": "frontend", "callee": "product-catalog", "call_count": 1200},
                    {"caller": "frontend", "callee": "recommendation", "call_count": 300},
                    {"caller": "frontend", "callee": "checkout", "call_count": 150},
                    {"caller": "checkout", "callee": "payment", "call_count": 150},
                    {"caller": "checkout", "callee": "shipping", "call_count": 150},
                    {"caller": "checkout", "callee": "cart", "call_count": 150},
                ]

        # Calculate node degrees and call volumes
        node_stats = []
        for node in sorted(list(nodes_set)):
            in_calls = sum(e["call_count"] for e in edges if e["callee"] == node)
            out_calls = sum(e["call_count"] for e in edges if e["caller"] == node)
            dependents = [e["caller"] for e in edges if e["callee"] == node]
            dependencies = [e["callee"] for e in edges if e["caller"] == node]

            criticality = "LOW"
            if len(dependents) >= 2 or in_calls > 500:
                criticality = "HIGH"
            elif len(dependents) == 1 or in_calls > 100:
                criticality = "MEDIUM"

            node_stats.append({
                "name": node,
                "in_degree": len(dependents),
                "out_degree": len(dependencies),
                "total_in_calls": in_calls,
                "total_out_calls": out_calls,
                "dependents": sorted(list(set(dependents))),
                "dependencies": sorted(list(set(dependencies))),
                "criticality": criticality
            })

        topology_graph = {
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node_count": len(node_stats),
            "edge_count": len(edges),
            "nodes": node_stats,
            "edges": edges,
        }

        # Cache topology to disk
        try:
            with open(TOPOLOGY_FILE, "w", encoding="utf-8") as f:
                json.dump(topology_graph, f, indent=2)
            logger.info(f"Discovered topology written to: {TOPOLOGY_FILE}")
        except Exception as e:
            logger.warning(f"Could not cache topology to file: {e}")

        return topology_graph


if __name__ == "__main__":
    discovery = TopologyDiscovery()
    graph = discovery.discover()
    print("\n--- Discovered Topology Summary ---")
    print(f"Source: {graph['source']}")
    print(f"Nodes ({graph['node_count']}): {[n['name'] for n in graph['nodes']]}")
    print(f"Edges ({graph['edge_count']}):")
    for edge in graph["edges"][:8]:
        print(f"  {edge['caller']} -> {edge['callee']} ({edge['call_count']} calls)")
    if len(graph["edges"]) > 8:
        print(f"  ... and {len(graph['edges']) - 8} more edges")
