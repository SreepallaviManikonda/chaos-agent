"""Stage 3: Docker-py Chaos Failure Injector with Automated Rollbacks."""

import json
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import docker
from docker.models.containers import Container

from config import (
    ALLOWED_TARGET_SERVICES,
    PROTECTED_CONTAINERS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ChaosInjector")

FLAGD_CONFIG_PATH = Path("/Users/sreepallavimanikonda/opentelemetry-demo/src/flagd/demo.flagd.json")


class ChaosInjector:
    """Manages Docker-level and application-level chaos failure injections."""

    def __init__(self):
        try:
            self.client = docker.from_env(timeout=10)
            logger.info("Connected to Docker daemon successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Docker daemon: {e}")
            self.client = None

        # Track currently active injections: {service_name: {type, details, original_config}}
        self.active_injections: Dict[str, Dict[str, Any]] = {}

    def find_container(self, service_name: str) -> Optional[Container]:
        """Resolves target service name to a running Docker container."""
        if not self.client:
            return None

        if service_name not in ALLOWED_TARGET_SERVICES:
            return None
        project = getattr(self, "project", os.getenv("CHAOS_COMPOSE_PROJECT", "opentelemetry-demo"))
        containers = self.client.containers.list(all=True, filters={"label": [
            f"com.docker.compose.project={project}", f"com.docker.compose.service={service_name}"]})
        return containers[0] if len(containers) == 1 else None

    def inject(self, service_name: str, experiment_type: str, **kwargs) -> bool:
        """Dispatches chaos injection according to experiment type."""
        if service_name not in ALLOWED_TARGET_SERVICES or service_name in PROTECTED_CONTAINERS or service_name in self.active_injections:
            logger.warning(f"Aborting injection: '{service_name}' is a protected infrastructure service.")
            return False

        logger.info(f"Injecting chaos: type='{experiment_type}' target='{service_name}'")

        if experiment_type == "container_pause":
            return self.inject_container_pause(service_name)
        elif experiment_type == "cpu_throttle":
            quota = kwargs.get("cpu_quota", 10000)  # Default 10% CPU
            return self.inject_cpu_throttle(service_name, cpu_quota=quota)
        elif experiment_type == "network_latency":
            delay_ms = kwargs.get("delay_ms", 500)
            return self.inject_network_latency(service_name, delay_ms=delay_ms)
        else:
            logger.error(f"Unknown experiment type: {experiment_type}")
            return False

    def inject_container_pause(self, service_name: str) -> bool:
        """Freezes container execution via Docker container.pause()."""
        container = self.find_container(service_name)
        if not container:
            logger.error(f"Container for service '{service_name}' not found.")
            return False

        try:
            container.reload()
            if container.status != "running":
                return False

            self.active_injections[service_name] = {
                "type": "container_pause",
                "container_id": container.id,
                "container_name": container.name
            }
            container.pause()
            logger.info(f"[INJECTED] Container '{container.name}' successfully paused.")
            return True
        except Exception as e:
            logger.error(f"Failed to pause container '{container.name}': {e}")
            return False

    def inject_cpu_throttle(self, service_name: str, cpu_quota: int = 10000, cpu_period: int = 100000) -> bool:
        """Throttles container CPU bandwidth (e.g. 10000 / 100000 = 10% CPU quota)."""
        container = self.find_container(service_name)
        if not container:
            logger.error(f"Container for service '{service_name}' not found.")
            return False

        try:
            container.reload()
            if container.status != "running":
                return False
            prev_quota = container.attrs.get("HostConfig", {}).get("CpuQuota", 0)
            prev_period = container.attrs.get("HostConfig", {}).get("CpuPeriod", 0)

            self.active_injections[service_name] = {
                "type": "cpu_throttle",
                "container_id": container.id,
                "container_name": container.name,
                "prev_quota": prev_quota,
                "prev_period": prev_period
            }
            container.update(cpu_quota=cpu_quota, cpu_period=cpu_period)
            logger.info(f"[INJECTED] CPU throttled for '{container.name}': quota={cpu_quota}, period={cpu_period}")
            return True
        except Exception as e:
            logger.error(f"Failed to throttle CPU for '{container.name}': {e}")
            return False

    def _tc(self, container_id, command):
        return self.client.containers.run(os.getenv("CHAOS_NETSHOOT_IMAGE", "local-netshoot:latest"),
            command=command, network_mode=f"container:{container_id}", cap_add=["NET_ADMIN"], remove=True, detach=False)

    def inject_network_latency(self, service_name, delay_ms=500):
        container = self.find_container(service_name)
        if container is None:
            return False
        try:
            container.reload()
            if container.status != "running" or not 1 <= int(delay_ms) <= 5000:
                return False
            rules = json.loads(self._tc(container.id, ["tc", "-j", "qdisc", "show", "dev", "eth0"]))
            if any(r.get("kind") != "noqueue" for r in rules):
                return False
            self.active_injections[service_name] = {"type": "network_latency", "container_id": container.id}
            self._tc(container.id, ["tc", "qdisc", "add", "dev", "eth0", "root", "handle", "7a01:", "netem", "delay", f"{int(delay_ms)}ms"])
            return True
        except Exception:
            logger.exception("Network injection failed")
            self.revert(service_name)
            return False

    def revert(self, service_name):
        record = self.active_injections.get(service_name)
        if record is None:
            return True
        try:
            container = self.client.containers.get(record["container_id"])
            container.reload()
            if record["type"] == "container_pause":
                if container.status == "paused":
                    container.unpause()
            elif record["type"] == "cpu_throttle":
                container.update(cpu_quota=record["prev_quota"], cpu_period=record["prev_period"])
            elif record["type"] == "network_latency":
                rules = json.loads(self._tc(container.id, ["tc", "-j", "qdisc", "show", "dev", "eth0"]))
                if any(r.get("kind") == "netem" and r.get("handle") == "7a01:" for r in rules):
                    self._tc(container.id, ["tc", "qdisc", "del", "dev", "eth0", "root", "handle", "7a01:"])
                elif any(r.get("kind") != "noqueue" for r in rules):
                    raise RuntimeError("Network rule ownership changed")
            del self.active_injections[service_name]
            return True
        except Exception:
            logger.exception("Rollback failed; retained for retry")
            return False

    def emergency_rollback_all(self):
        return all([self.revert(service) for service in list(self.active_injections)])
