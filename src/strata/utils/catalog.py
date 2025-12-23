"""Persistent catalog for storing MCP tool definitions."""

import json
import logging
import os
from typing import Dict, List, Any, Optional

from platformdirs import user_cache_dir

from strata.utils.shared_search import UniversalToolSearcher

logger = logging.getLogger(__name__)


class ToolCatalog:
    """Manages persistent storage and retrieval of tool definitions."""

    def __init__(self, app_name: str = "strata"):
        self.cache_dir = user_cache_dir(app_name)
        self.catalog_file = os.path.join(self.cache_dir, "tool_catalog.json")
        self._catalog: Dict[str, List[Any]] = {}
        self._ensure_cache_dir()
        self.load()

    def _ensure_cache_dir(self):
        """Ensure the cache directory exists."""
        os.makedirs(self.cache_dir, exist_ok=True)

    def load(self) -> None:
        """Load the catalog from disk."""
        if os.path.exists(self.catalog_file):
            try:
                with open(self.catalog_file, "r", encoding="utf-8") as f:
                    self._catalog = json.load(f)
                logger.info(f"Loaded tool catalog from {self.catalog_file}")
            except Exception as e:
                logger.error(f"Failed to load catalog: {e}")
                self._catalog = {}
        else:
            self._catalog = {}

    def save(self) -> None:
        """Save the catalog to disk."""
        try:
            with open(self.catalog_file, "w", encoding="utf-8") as f:
                json.dump(self._catalog, f, indent=2)
            logger.info(f"Saved tool catalog to {self.catalog_file}")
        except Exception as e:
            logger.error(f"Failed to save catalog: {e}")

    def update_server(self, server_name: str, tools: List[Any]) -> None:
        """Update the tools for a specific server."""
        self._catalog[server_name] = tools
        self.save()

    def get_tools(self, server_name: str) -> List[Any]:
        """Get tools for a specific server from the catalog."""
        return self._catalog.get(server_name, [])

    def get_all_tools(self) -> Dict[str, List[Any]]:
        """Get all tools in the catalog."""
        return self._catalog

    def search(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """Search for tools across the entire catalog."""
        if not self._catalog:
            return []

        searcher = UniversalToolSearcher(self._catalog)
        results = searcher.search(query, max_results=max_results)
        
        # Add a flag to indicate these are catalog results
        for result in results:
            result["source"] = "catalog"
            
        return results

    def remove_server(self, server_name: str) -> None:
        """Remove a server from the catalog."""
        if server_name in self._catalog:
            del self._catalog[server_name]
            self.save()
