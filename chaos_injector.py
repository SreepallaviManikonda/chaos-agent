"""Stage 3: Docker-py Chaos Failure Injector with Automated Rollbacks."""

import json
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
            self.client = docker.from_env()
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

        clean_name = service_name.lower().replace("service", "").strip()

        try:
            containers = self.client.containers.list(all=True)
            # 1. Exact container name match
            for c in containers:
                if c.name.lower() == service_name.lower() or c.name.lower() == clean_name:
                    return c

            # 2. Compose service label match
            for c in containers:
                svc_label = c.labels.get("com.docker.compose.service", "").lower()
                if svc_label == service_name.lower() or svc_label == clean_name:
                    return c

            # 3. Substring match
            for c in containers:
                if clean_name in c.name.lower():
                    return c

        except Exception as e:
            logger.error(f"Error querying Docker containers: {e}")

        return None

    def inject(self, service_name: str, experiment_type: str, **kwargs) -> bool:
        """Dispatches chaos injection according to experiment type."""
        if service_name in PROTECTED_CONTAINERS:
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
            if container.status == "paused":
                logger.info(f"Container '{container.name}' is already paused.")
                return True

            container.pause()
            self.active_injections[service_name] = {
                "type": "container_pause",
                "container_id": container.id,
                "container_name": container.name
            }
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
            prev_quota = container.attrs.get("HostConfig", {}).get("CpuQuota", 0)
            prev_period = container.attrs.get("HostConfig", {}).get("CpuPeriod", 0)

            container.update(cpu_quota=cpu_quota, cpu_period=cpu_period)
            self.active_injections[service_name] = {
                "type": "cpu_throttle",
                "container_id": container.id,
                "container_name": container.name,
                "prev_quota": prev_quota,
                "prev_period": prev_period
            }
            logger.info(f"[INJECTED] CPU throttled for '{container.name}': quota={cpu_quota}, period={cpu_period}")
            return True
        except Exception as e:
            logger.error(f"Failed to throttle CPU for '{container.name}': {e}")
            return False

    def inject_network_latency(self, service_name: str, delay_ms: int = 500) -> bool:
        """Injects network latency or service-level delays via Flagd feature toggles."""
        container = self.find_container(service_name)
        target_name = container.name if container else service_name

        # Mapping services to known Flagd delay or failure flags
        flag_map = {
            "product-catalog": "productCatalogLockContention",
            "cart": "cartFailure",
            "shipping": "intlShippingSlowdown",
            "payment": "paymentFailure",
            "recommendation": "recommendationCacheFailure",
            "ad": "adHighCpu"
        }

        flag_name = flag_map.get(service_name.lower().replace("service", ""))

        if flag_name and FLAGD_CONFIG_PATH.exists():
            try:
                with open(FLAGD_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if "flags" in data and flag_name in data["flags"]:
                    data["flags"][flag_name]["defaultVariant"] = "on"
                    with open(FLAGD_CONFIG_PATH, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)

                    self.active_injections[service_name] = {
                        "type": "network_latency",
                        "method": "flagd_toggle",
                        "flag_name": flag_name,
                        "container_name": target_name
                    }
                    logger.info(f"[INJECTED] Toggled Flagd feature flag '{flag_name}' to 'on' for {service_name}.")
                    return True
            except Exception as e:
                logger.warning(f"Could not toggle Flagd flag {flag_name}: {e}")

        # Fallback: CPU throttle or pause pulse if flagd is not accessible
        logger.info(f"Falling back to CPU choke delay simulation for {service_name}...")
        return self.inject_cpu_throttle(service_name, cpu_quota=10000)

    def revert(self, service_name: str) -> bool:
        """Reverts active chaos injection on target service."""
        injection = self.active_injections.get(service_name)
        container = self.find_container(service_name)

        success = True
        logger.info(f"Reverting chaos on '{service_name}'...")

        if container:
            try:
                container.reload()
                if container.status == "paused":
                    container.unpause()
                    logger.info(f"[REVERTED] Unpaused container '{container.name}'.")

                # Reset CPU quota to unlimited (-1 or 0)
                container.update(cpu_quota=-1)
                logger.info(f"[REVERTED] Reset CPU quota for container '{container.name}'.")
            except Exception as e:
                logger.error(f"Error reverting container '{container.name}': {e}")
                success = False

        # Reset any modified Flagd flags
        if injection and injection.get("method") == "flagd_toggle" and FLAGD_CONFIG_PATH.exists():
            flag_name = injection.get("flag_name")
            try:
                with open(FLAGD_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if flag_name and "flags" in data and flag_name in data["flags"]:
                    data["flags"][flag_name]["defaultVariant"] = "off"
                    with open(FLAGD_CONFIG_PATH, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                logger.info(f"[REVERTED] Reset Flagd flag '{flag_name}' to 'off'.")
            except Exception as e:
                logger.error(f"Error resetting Flagd flag {flag_name}: {e}")
                success = False

        if service_name in self.active_injections:
            del self.active_injections[service_name]

        return success

    def emergency_rollback_all(self) -> None:
        """Failsafe kill-switch: restores all containers and resets all flags."""
        logger.warning("🚨 EMERGENCY ROLLBACK TRIGGERED: Restoring all services to normal state...")
        if not self.client:
            return

        try:
            # 1. Unpause any paused container
            for c in self.client.containers.list(all=True):
                try:
                    c.reload()
                    if c.status == "paused":
                        c.unpause()
                        logger.warning(f"Emergency unpaused container: {c.name}")
                    # Reset CPU quota
                    c.update(cpu_quota=-1)
                except Exception as e:
                    logger.error(f"Error resetting container {c.name}: {e}")

            # 2. Reset all Flagd flags to 'off'
            if FLAGD_CONFIG_PATH.exists():
                try:
                    with open(FLAGD_CONFIG_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    modified = False
                    for flag_val in data.get("flags", {}).values():
                        if isinstance(flag_val, dict) and flag_val.get("defaultVariant") == "on":
                            flag_val["defaultVariant"] = "off"
                            modified = True
                    if modified:
                        with open(FLAGD_CONFIG_PATH, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        logger.warning("Emergency reset all Flagd flags to 'off'.")
                except Exception as e:
                    logger.error(f"Error resetting Flagd config: {e}")

            self.active_injections.clear()
            logger.info("Emergency rollback completed. All systems nominal.")
        except Exception as e:
            logger.error(f"Fatal error during emergency rollback: {e}")


if __name__ == "__main__":
    injector = ChaosInjector()
    container = injector.find_container("cart")
    if container:
        print(f"Found container: {container.name} (Status: {container.status})")
    else:
        print("Cart container not found.")
