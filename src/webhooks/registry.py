"""
Webhook source registry - manages available webhook sources.
"""

import logging
from typing import Dict, Optional

from src.providers.config_loader import get_config

from .base import BaseWebhookSource

logger = logging.getLogger(__name__)

# Source class mapping — add new sources here
_SOURCE_CLASSES = {
    "devrev": "src.webhooks.devrev.DevRevWebhookSource",
}


class WebhookSourceRegistry:
    """Registry of available webhook sources, initialized from config."""

    def __init__(self):
        self._sources: Dict[str, BaseWebhookSource] = {}
        self._load_from_config()

    def _load_from_config(self):
        """Load enabled sources from webhooks config."""
        config = get_config()
        enabled = config.get("webhooks", {}).get("enabled_sources", [])

        for name in enabled:
            cls_path = _SOURCE_CLASSES.get(name)
            if not cls_path:
                logger.warning(f"Unknown webhook source '{name}', skipping")
                continue

            try:
                module_path, cls_name = cls_path.rsplit(".", 1)
                import importlib

                module = importlib.import_module(module_path)
                cls = getattr(module, cls_name)
                instance = cls()
                self._sources[name] = instance
                logger.info(f"Registered webhook source: {name}")
            except Exception as e:
                logger.error(f"Failed to load webhook source '{name}': {e}")

    def get(self, name: str) -> Optional[BaseWebhookSource]:
        """Get a registered webhook source by name."""
        return self._sources.get(name)

    def list_sources(self) -> list:
        """List registered source names."""
        return list(self._sources.keys())
