# gnosys-strata

Enhanced fork of [Klavis Strata](https://github.com/Klavis-AI/klavis) with JIT server management and catalog mode.

## What's Different

The original Strata has serious scalability issues:
- **Memory hog**: Every MCP stays loaded in memory (2.7% each)
- **No caching**: Rebuilds tool index on every startup
- **Sync loading**: Couldn't even load 5 MCPs without OOM

**gnosys-strata** fixes this:

| Feature | Original | gnosys-strata |
|---------|----------|---------------|
| Server loading | All at once, sync | JIT, async |
| Memory usage | O(n) always | O(active) |
| Tool catalog | Rebuilt every time | Disk-cached |
| 20+ MCPs | OOM crash | Works fine |
| MCP Sets | No | Yes |

## New Features

### Catalog Mode
Tool schemas are cached to disk. Search across ALL configured servers without loading them:

```bash
# Search tools across offline servers
strata search "github issues"
```

### JIT Server Management
Servers only load when you actually use them:

```python
# Via tools
manage_servers(action="connect", server_name="github")  # Load on demand
manage_servers(action="disconnect", server_name="github")  # Free memory
manage_servers(action="list")  # See what's active
```

### MCP Sets
Group servers into named sets, swap between them:

```python
# Coming soon
activate_set("development")  # github, filesystem, git
activate_set("production")   # monitoring, alerting, deploy
```

## Installation

```bash
pip install gnosys-strata
```

## Configuration

Same as original Strata - config lives at `~/.config/strata/servers.json`:

```json
{
  "mcp": {
    "servers": {
      "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_TOKEN": "..."},
        "enabled": true
      }
    }
  }
}
```

## Usage

```bash
# Run as MCP server (stdio mode)
strata

# Run as HTTP server
strata run --port 8080
```

## Tools

Core tools (always available):
- `discover_server_actions` - Find tools across servers
- `get_action_details` - Get tool schema
- `execute_action` - Run a tool
- `search_documentation` - Search tool docs

New in gnosys-strata:
- `manage_servers` - Connect/disconnect servers on demand
- `search_mcp_catalog` - Search cached tool index (offline)

## License

Apache-2.0 (same as original)

## Credits

Fork of [Klavis AI Strata](https://github.com/Klavis-AI/klavis). Enhanced by Isaac Wostrel-Rubin.
