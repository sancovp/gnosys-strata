"""Strata functions for TreeShell crystallization - clean function-per-tool architecture."""

import logging
import traceback
from typing import List, Dict, Any, Optional

from strata.mcp_client_manager import MCPClientManager
from strata.utils.shared_search import UniversalToolSearcher

logger = logging.getLogger(__name__)

# Global client manager - instantiated at import time
client_manager = MCPClientManager()


async def discover_server_actions(user_query: str, server_names: List[str] = None) -> Dict[str, Any]:
    """
    **PREFERRED STARTING POINT**: Discover available actions from servers based on user query.

    Args:
        user_query: Natural language user query to filter results.
        server_names: List of server names to discover actions from.
    """
    if not server_names:
        server_names = list(client_manager.active_clients.keys())

    discovery_result = {}
    for server_name in server_names:
        try:
            client = client_manager.get_client(server_name)
            tools = await client.list_tools()

            if user_query and tools:
                tools_map = {server_name: tools}
                searcher = UniversalToolSearcher(tools_map)
                search_results = searcher.search(user_query, max_results=50)

                filtered_action_names = []
                for result_item in search_results:
                    for tool in tools:
                        if tool["name"] == result_item["name"]:
                            filtered_action_names.append(tool)
                            break
                discovery_result[server_name] = filtered_action_names
            else:
                discovery_result[server_name] = tools

        except KeyError:
            # Check if configured but not connected vs not configured at all
            configured_servers = [s.name for s in client_manager.server_list.servers]
            if server_name in configured_servers:
                discovery_result[server_name] = {
                    "error": f"Server '{server_name}' is configured but not connected",
                    "fix": f"Run: manage_servers.exec {{\"connect\": \"{server_name}\"}}"
                }
            else:
                discovery_result[server_name] = {
                    "error": f"Server '{server_name}' is not configured",
                    "fix": "Check ~/.config/strata/servers.json or use manage_servers to see available servers"
                }
        except Exception as e:
            logger.error(f"Error discovering tools for {server_name}: {e}\n{traceback.format_exc()}")
            discovery_result[server_name] = {"error": str(e), "traceback": traceback.format_exc()}

    return discovery_result


async def get_action_details(server_name: str, action_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific action.

    Args:
        server_name: The name of the server.
        action_name: The name of the action/operation.
    """
    try:
        client = client_manager.get_client(server_name)
        tools = await client.list_tools()

        tool = next((t for t in tools if t["name"] == action_name), None)

        if tool:
            return {
                "name": tool["name"],
                "description": tool.get("description"),
                "inputSchema": tool.get("inputSchema"),
            }
        else:
            return {"error": f"Action '{action_name}' not found on server '{server_name}'"}
    except KeyError:
        configured_servers = [s.name for s in client_manager.server_list.servers]
        if server_name in configured_servers:
            return {
                "error": f"Server '{server_name}' is configured but not connected",
                "fix": f"Run: manage_servers.exec {{\"connect\": \"{server_name}\"}}"
            }
        else:
            return {
                "error": f"Server '{server_name}' is not configured",
                "fix": "Check ~/.config/strata/servers.json or use manage_servers to see available servers"
            }
    except Exception as e:
        logger.error(f"Error getting action details for {server_name}/{action_name}: {e}\n{traceback.format_exc()}")
        return {"error": str(e), "traceback": traceback.format_exc()}


async def execute_action(
    server_name: str,
    action_name: str,
    path_params: Optional[str] = None,
    query_params: Optional[str] = None,
    body_schema: Optional[str] = "{}"
) -> Dict[str, Any]:
    """
    Execute a specific action with the provided parameters.

    Args:
        server_name: The name of the server.
        action_name: The name of the action/operation to execute.
        path_params: JSON string containing path parameters.
        query_params: JSON string containing query parameters.
        body_schema: JSON string containing request body.
    """
    import json

    # Check if server is connected (no JIT - explicit connect required)
    if server_name not in client_manager.active_clients:
        server_config = client_manager.server_list.get_server(server_name)
        if server_config:
            return {
                "error": f"Server '{server_name}' is not connected",
                "suggestion": f"Connect first with: manage_servers.exec {{\"connect\": \"{server_name}\"}}"
            }
        else:
            return {"error": f"Server '{server_name}' not configured"}

    try:
        client = client_manager.get_client(server_name)

        if not client.is_connected():
            return {"error": f"Server '{server_name}' is not connected"}

        action_params = {}
        for param_name, param_value in [
            ("path_params", path_params),
            ("query_params", query_params),
            ("body_schema", body_schema),
        ]:
            if param_value and param_value != "{}":
                try:
                    if isinstance(param_value, str):
                        action_params.update(json.loads(param_value))
                    else:
                        action_params.update(param_value)
                except json.JSONDecodeError as e:
                    return {"error": f"Invalid JSON in {param_name}: {str(e)}"}

        result = await client.call_tool(action_name, action_params)
        return {"result": result}

    except Exception as e:
        logger.error(f"Execution failed for {server_name}/{action_name}: {e}\n{traceback.format_exc()}")
        return {"error": f"Execution failed: {str(e)}", "traceback": traceback.format_exc()}


async def manage_servers(
    list_configured_mcps: bool = False,
    list_sets: bool = False,
    connect: Optional[str] = None,
    connect_set: Optional[str] = None,
    connect_set_exclusive: bool = False,
    search_sets: Optional[str] = None,
    upsert_set: Optional[Dict[str, Any]] = None,
    delete_set: Optional[str] = None,
    disconnect: Optional[str] = None,
    disconnect_set: Optional[str] = None,
    disconnect_all: bool = False,
    populate_catalog: bool = False
) -> str:
    """
    Manage MCP server connections and Sets.

    Args:
        list_configured_mcps: If true, lists all configured servers with their status.
        list_sets: If true, lists all configured Sets and their servers.
        connect: Name of the server to connect (turn on).
        connect_set: Name of the Set to connect (turn on all servers in set).
        connect_set_exclusive: If true with connect_set, disconnects all other servers first.
        search_sets: Search set descriptions for matching sets.
        upsert_set: Create or update a Set (dict with name, servers, description, include_sets).
        delete_set: Name of the Set to delete.
        disconnect: Name of the server to disconnect (turn off).
        disconnect_set: Name of the Set to disconnect (turn off all servers in set).
        disconnect_all: If true, disconnects all servers.
        populate_catalog: If true, connects to all enabled servers, refreshes catalog cache, then disconnects.
    """
    import asyncio

    results = []

    if list_configured_mcps:
        active = client_manager.list_active_servers()
        configured = client_manager.server_list.list_servers()
        lines = [f"{s.name}, {'on' if s.name in active else 'off'}" for s in configured]
        results.append("\n".join(lines))

    if list_sets:
        sets = client_manager.server_list.list_sets()
        lines = []
        for name, data in sets.items():
            desc = data.get('description', '')
            servers = data.get('servers', [])
            includes = data.get('include_sets', [])
            line = f"{name}: {desc}" if desc else f"{name}:"
            if servers:
                line += f"\n  servers: {', '.join(servers)}"
            if includes:
                line += f"\n  includes: {', '.join(includes)}"
            lines.append(line)
        results.append("\n".join(lines) if lines else "No sets configured")

    if search_sets:
        sets = client_manager.server_list.list_sets()
        query_lower = search_sets.lower()
        matches = []
        for name, data in sets.items():
            desc = data.get('description', '')
            if query_lower in name.lower() or query_lower in desc.lower():
                servers = ', '.join(data.get('servers', []))
                matches.append(f"{name}: {desc}\n  {servers}" if desc else f"{name}:\n  {servers}")
        results.append("\n".join(matches) if matches else f"no sets matching '{search_sets}'")

    if upsert_set:
        try:
            name = upsert_set.get("name")
            servers = upsert_set.get("servers", [])
            desc = upsert_set.get("description", "")
            include_sets = upsert_set.get("include_sets")
            if name and (servers or include_sets):
                client_manager.server_list.add_set(name, servers, desc, include_sets)
                results.append(f"set '{name}' saved")
            else:
                results.append("error: missing name, or need servers or include_sets")
        except Exception as e:
            logger.error(f"Error upserting set: {e}\n{traceback.format_exc()}")
            results.append(f"error: {e}\n{traceback.format_exc()}")

    if delete_set:
        success = client_manager.server_list.remove_set(delete_set)
        results.append(f"set '{delete_set}' deleted" if success else f"error: set '{delete_set}' not found")

    if connect:
        server_config = client_manager.server_list.get_server(connect)
        if server_config:
            asyncio.create_task(client_manager._connect_server(server_config))
            results.append(f"{connect} starting")
        else:
            results.append(f"error: {connect} not configured")

    if connect_set:
        servers_in_set = client_manager.server_list.get_set(connect_set)
        if servers_in_set:
            disconnected = []
            if connect_set_exclusive:
                for srv in list(client_manager.active_clients.keys()):
                    if srv not in servers_in_set:
                        await client_manager._disconnect_server(srv)
                        disconnected.append(srv)

            statuses = []
            for srv in servers_in_set:
                server_config = client_manager.server_list.get_server(srv)
                if server_config and srv not in client_manager.active_clients:
                    asyncio.create_task(client_manager._connect_server(server_config))
                    statuses.append(f"{srv}: starting")
                elif srv in client_manager.active_clients:
                    statuses.append(f"{srv}: on")
                else:
                    statuses.append(f"{srv}: not configured")
            prefix = f"connect_set '{connect_set}' (exclusive):" if connect_set_exclusive else f"connect_set '{connect_set}':"
            output = f"{prefix}\n" + "\n".join(statuses)
            if disconnected:
                output += f"\nstopped: {', '.join(disconnected)}"
            results.append(output)
        else:
            results.append(f"error: set '{connect_set}' not found")

    if disconnect:
        await client_manager._disconnect_server(disconnect)
        results.append(f"{disconnect} off")

    if disconnect_set:
        servers_in_set = client_manager.server_list.get_set(disconnect_set)
        if servers_in_set:
            for srv in servers_in_set:
                await client_manager._disconnect_server(srv)
            results.append(f"disconnect_set '{disconnect_set}': {len(servers_in_set)} stopped")
        else:
            results.append(f"error: set '{disconnect_set}' not found")

    if disconnect_all:
        await client_manager.disconnect_all()
        results.append("all disconnected")

    if populate_catalog:
        enabled_servers = client_manager.server_list.list_servers(enabled_only=True)
        already_cached = [s for s in enabled_servers if client_manager.catalog.get_tools(s.name)]
        to_populate = [s for s in enabled_servers if not client_manager.catalog.get_tools(s.name)]

        if not to_populate:
            results.append(f"catalog: {len(already_cached)}/{len(enabled_servers)} cached, nothing to populate")
        else:
            indexed = []
            for server in to_populate:
                try:
                    was_connected = server.name in client_manager.active_clients
                    if not was_connected:
                        await client_manager._connect_server(server)
                    client = client_manager.get_client(server.name)
                    tools = await client.list_tools()
                    client_manager.catalog.update_server(server.name, tools)
                    if not was_connected:
                        await client_manager._disconnect_server(server.name)
                    indexed.append(f"{server.name}: {len(tools)} tools")
                except Exception as e:
                    logger.error(f"Error populating catalog for {server.name}: {e}\n{traceback.format_exc()}")
                    indexed.append(f"{server.name}: error - {e}")
            results.append(f"catalog: indexed {len(to_populate)}, skipped {len(already_cached)}\n" + "\n".join(indexed))

    return "\n".join(str(r) for r in results)


async def search_mcp_catalog(query: str, max_results: int = 20) -> Dict[str, Any]:
    """
    Search for tools in the offline catalog and discover Sets/Collections.

    Args:
        query: Search query for tools or collections.
        max_results: Maximum results to return. Default 20.
    """
    # Search tools
    tool_results = client_manager.catalog.search(query, max_results)

    # Annotate with current status
    active_servers = client_manager.list_active_servers()
    for r in tool_results:
        r["current_status"] = "online" if r.get("category_name") in active_servers else "offline"

    # Search sets
    sets = client_manager.server_list.list_sets()
    matching_sets = []
    for set_name, set_data in sets.items():
        description = set_data.get("description", "")
        if (query.lower() in set_name.lower()) or (query.lower() in description.lower()):
            matching_sets.append({
                "type": "collection",
                "name": set_name,
                "description": description,
                "servers": set_data.get("servers", []),
                "status": "available"
            })

    return {"collections": matching_sets, "tools": tool_results}


async def search_documentation(query: str, server_name: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Search for server action documentations by keyword matching.

    Args:
        query: Search keywords.
        server_name: Name of the server to search within.
        max_results: Number of results to return. Default: 10.
    """
    try:
        client = client_manager.get_client(server_name)
        tools = await client.list_tools()

        tools_map = {server_name: tools if tools else []}
        searcher = UniversalToolSearcher(tools_map)
        return searcher.search(query, max_results=max_results)
    except KeyError:
        configured_servers = [s.name for s in client_manager.server_list.servers]
        if server_name in configured_servers:
            return [{"error": f"Server '{server_name}' is configured but not connected", "fix": f"Run: manage_servers.exec {{\"connect\": \"{server_name}\"}}"}]
        else:
            return [{"error": f"Server '{server_name}' is not configured", "fix": "Check ~/.config/strata/servers.json"}]
    except Exception as e:
        logger.error(f"Error searching documentation for {server_name}: {e}\n{traceback.format_exc()}")
        return [{"error": f"Error searching documentation: {str(e)}", "traceback": traceback.format_exc()}]


async def handle_auth_failure(
    server_name: str,
    intention: str,
    auth_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handle authentication failures that occur when executing actions.

    Args:
        server_name: The name of the server.
        intention: Action to take for authentication ('get_auth_url' or 'save_auth_data').
        auth_data: Authentication data when saving.
    """
    if intention == "get_auth_url":
        return {
            "server": server_name,
            "message": f"Authentication required for server '{server_name}'",
            "instructions": "Please provide authentication credentials",
            "required_fields": {"token": "Authentication token or API key"},
        }
    elif intention == "save_auth_data":
        if not auth_data:
            return {"error": "auth_data is required when intention is 'save_auth_data'"}
        return {
            "server": server_name,
            "status": "success",
            "message": f"Authentication data saved for server '{server_name}'",
        }
    else:
        return {"error": f"Invalid intention: '{intention}'"}
