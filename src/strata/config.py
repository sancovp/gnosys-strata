import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

from platformdirs import user_config_dir
from watchfiles import awatch


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""

    name: str
    type: str = "stdio"  # "stdio", "sse", "http"
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    auth: Optional[str] = None  # Auth token/key if needed
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPServerConfig":
        """Create from dictionary."""
        # Handle legacy format where type might be missing
        type_val = data.get("type", "stdio")
        if "url" in data and not type_val:
            type_val = "sse"  # Guess sse if url present
        
        return cls(
            name=data["name"],
            type=type_val,
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            url=data.get("url"),
            headers=data.get("headers", {}),
            auth=data.get("auth"),
            enabled=data.get("enabled", True),
        )


class MCPServerList:
    """Manage a list of MCP server configurations and sets."""

    def __init__(self, config_path: Optional[Path] = None, use_mcp_format: bool = True):
        """Initialize the MCP server list.

        Args:
            config_path: Path to the configuration file. If None, uses default.
            use_mcp_format: If True, save in MCP format. If False, use legacy format.
        """
        if config_path is None:
            # Use platformdirs for cross-platform config directory
            config_dir = Path(user_config_dir("strata"))
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_path = config_dir / "servers.json"
        else:
            self.config_path = Path(config_path)

        self.servers: Dict[str, MCPServerConfig] = {}
        self.sets: Dict[str, List[str]] = {}
        self.use_mcp_format = use_mcp_format
        self.load()

    def load(self) -> None:
        """Load server configurations and sets from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                    # Check if it's MCP format (has "mcp" key with "servers" inside)
                    if "mcp" in data and "servers" in data["mcp"]:
                        # Parse MCP format
                        for name, config in data["mcp"]["servers"].items():
                            # MCP format doesn't have "name" field, add it
                            config_dict = {
                                "name": name,
                                "type": config.get("type", "stdio"),
                                "env": config.get("env", {}),
                                "enabled": config.get("enabled", True),
                            }

                            # Add type-specific fields
                            if config.get("type") in ["sse", "http"]:
                                config_dict["url"] = config.get("url")
                                config_dict["headers"] = config.get("headers", {})
                                config_dict["auth"] = config.get("auth", "")
                            else:  # stdio/command
                                config_dict["command"] = config.get("command", "")
                                config_dict["args"] = config.get("args", [])

                            self.servers[name] = MCPServerConfig.from_dict(config_dict)
                        
                        # Parse sets if available
                        self.sets = data["mcp"].get("sets", {})
                            
                    # Otherwise check for legacy format
                    elif "servers" in data:
                        # Parse legacy format
                        for name, config in data["servers"].items():
                            self.servers[name] = MCPServerConfig.from_dict(config)
                        # Legacy format doesn't support sets usually, or we could add it top-level
                        self.sets = data.get("sets", {})
            except Exception as e:
                print(f"Error loading config from {self.config_path}: {e}")

    def save(self) -> None:
        """Save server configurations and sets to file."""
        if self.use_mcp_format:
            # Save in MCP format
            servers_dict = {}
            for name, server in self.servers.items():
                server_config = {}

                # Add type field if not stdio (default)
                if server.type and server.type != "stdio":
                    server_config["type"] = server.type

                # Add type-specific fields
                if server.type in ["sse", "http"]:
                    server_config["url"] = server.url
                    if server.headers:
                        server_config["headers"] = server.headers
                    if server.auth:
                        server_config["auth"] = server.auth
                else:  # stdio/command
                    server_config["command"] = server.command
                    server_config["args"] = server.args

                if server.env:
                    server_config["env"] = server.env
                # Always save enabled field to be explicit
                server_config["enabled"] = server.enabled
                servers_dict[name] = server_config

            data = {
                "mcp": {
                    "servers": servers_dict,
                    "sets": self.sets
                }
            }
        else:
            # Save in legacy format
            data = {
                "servers": {
                    name: server.to_dict() for name, server in self.servers.items()
                },
                "sets": self.sets
            }

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add_server(self, server: MCPServerConfig) -> bool:
        """Add or update a server configuration."""
        if server.name in self.servers and self.servers[server.name] == server:
            return False
        self.servers[server.name] = server
        self.save()
        return True

    def remove_server(self, name: str) -> bool:
        """Remove a server configuration."""
        if name in self.servers:
            del self.servers[name]
            # Also remove from any sets
            for set_name in list(self.sets.keys()):
                s = self.sets[set_name]
                if isinstance(s, list) and name in s:
                    s.remove(name)
                elif isinstance(s, dict) and name in s.get("servers", []):
                    s["servers"].remove(name)
            self.save()
            return True
        return False

    def get_server(self, name: str) -> Optional[MCPServerConfig]:
        """Get a server configuration by name."""
        return self.servers.get(name)

    def list_servers(self, enabled_only: bool = False) -> List[MCPServerConfig]:
        """List all server configurations."""
        servers = list(self.servers.values())
        if enabled_only:
            servers = [s for s in servers if s.enabled]
        return servers

    def enable_server(self, name: str) -> bool:
        """Enable a server."""
        if name in self.servers:
            self.servers[name].enabled = True
            self.save()
            return True
        return False

    def disable_server(self, name: str) -> bool:
        """Disable a server."""
        if name in self.servers:
            self.servers[name].enabled = False
            self.save()
            return True
        return False

    # --- Sets Management ---

    def add_set(self, name: str, server_names: List[str], description: str = "", include_sets: Optional[List[str]] = None) -> None:
        """Add or update a set of servers.

        Args:
            name: Name of the set
            server_names: List of server names in the set
            description: Description of the set's purpose
            include_sets: List of other set names to include (composability)
        """
        self.sets[name] = {
            "description": description,
            "servers": server_names
        }
        if include_sets:
            self.sets[name]["include_sets"] = include_sets
        self.save()

    def remove_set(self, name: str) -> bool:
        """Remove a set."""
        if name in self.sets:
            del self.sets[name]
            self.save()
            return True
        return False

    def get_set(self, name: str, _visited: Optional[set] = None) -> Optional[List[str]]:
        """Get servers in a set, resolving included sets recursively."""
        if _visited is None:
            _visited = set()
        if name in _visited:
            return []  # Prevent infinite loops
        _visited.add(name)

        s = self.sets.get(name)
        if s is None:
            return None
        if isinstance(s, list):
            return s

        servers = list(s.get("servers", []))
        for included in s.get("include_sets", []):
            included_servers = self.get_set(included, _visited)
            if included_servers:
                for srv in included_servers:
                    if srv not in servers:
                        servers.append(srv)
        return servers
        
    def get_set_details(self, name: str) -> Optional[Dict[str, Any]]:
        """Get full set details including description."""
        details = self.sets.get(name)
        if isinstance(details, list):
             return {"description": "", "servers": details}
        return details

    def list_sets(self) -> Dict[str, Dict[str, Any]]:
        """List all sets with details.
        
        Returns:
            Dictionary mapping set name to set details (description, servers)
        """
        # Normalize output for consistency
        result = {}
        for name, data in self.sets.items():
            if isinstance(data, list):
                result[name] = {"description": "", "servers": data}
            else:
                result[name] = data
        return result

    # -----------------------

    async def watch_config(
        self,
        on_changed: Callable[[Dict[str, MCPServerConfig]], None],
    ):
        """Watch configuration file for changes and trigger callback."""
        async for changes in awatch(str(self.config_path.parent)):
            config_changed = False
            for _, path in changes:
                if Path(path) == self.config_path:
                    config_changed = True
                    break

            if not config_changed:
                continue

            self.servers.clear()
            self.sets.clear()
            self.load()
            on_changed(dict(self.servers))


# Global instance for easy access
mcp_server_list = MCPServerList()
