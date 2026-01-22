"""Shared tool implementations for Strata MCP Router."""

import asyncio
import json
import logging
import traceback
from typing import List, Dict, Any

import mcp.types as types

from .mcp_client_manager import MCPClientManager
from .config import mcp_server_list
from .utils.shared_search import UniversalToolSearcher

logger = logging.getLogger(__name__)


def _build_error_response(error_msg: str, traceback_info: str = None, **extra) -> Dict[str, Any]:
    """Build standardized error response with optional traceback.

    Args:
        error_msg: Human-readable error message
        traceback_info: Optional full traceback string
        **extra: Additional context fields

    Returns:
        Structured error dict with status, error, and optional traceback
    """
    response = {
        "status": "error",
        "error": error_msg,
        **extra
    }
    if traceback_info:
        response["traceback"] = traceback_info
    return response

# Tool Names
TOOL_DISCOVER_SERVER_ACTIONS = "discover_server_actions"
TOOL_GET_ACTION_DETAILS = "get_action_details"
TOOL_EXECUTE_ACTION = "execute_action"
TOOL_SEARCH_DOCUMENTATION = "search_documentation"
TOOL_HANDLE_AUTH_FAILURE = "handle_auth_failure"
# Tool Names for Management
TOOL_MANAGE_SERVERS = "manage_servers"
TOOL_SEARCH_MCP_CATALOG = "search_mcp_catalog"


def get_tool_definitions(user_available_servers: List[str]) -> List[types.Tool]:
    """Get tool definitions for the available servers."""
    return [
        types.Tool(
            name=TOOL_DISCOVER_SERVER_ACTIONS,
            description="**PREFERRED STARTING POINT**: Discover available actions from servers based on user query.",
            inputSchema={
                "type": "object",
                "required": ["user_query", "server_names"],
                "properties": {
                    "user_query": {
                        "type": "string",
                        "description": "Natural language user query to filter results.",
                    },
                    "server_names": {
                        "type": "array",
                        "items": {"type": "string", "enum": user_available_servers},
                        "description": "List of server names to discover actions from.",
                    },
                },
            },
        ),
        types.Tool(
            name=TOOL_GET_ACTION_DETAILS,
            description="Get detailed information about a specific action.",
            inputSchema={
                "type": "object",
                "required": ["server_name", "action_name"],
                "properties": {
                    "server_name": {
                        "type": "string",
                        "enum": user_available_servers,
                        "description": "The name of the server",
                    },
                    "action_name": {
                        "type": "string",
                        "description": "The name of the action/operation",
                    },
                },
            },
        ),
        types.Tool(
             name=TOOL_MANAGE_SERVERS,
             description="Manage MCP server connections and Sets.",
             inputSchema={
                 "type": "object",
                 "properties": {
                     "list_configured_mcps": {
                         "type": "boolean",
                         "description": "If true, lists all configured servers with their status.",
                     },
                     "list_sets": {
                         "type": "boolean",
                         "description": "If true, lists all configured Sets and their servers.",
                     },
                     "connect": {
                         "type": "string",
                         "description": "Name of the server to connect (turn on).",
                     },
                     "connect_set": {
                         "type": "string",
                         "description": "Name of the Set to connect (turn on all servers in set).",
                     },
                     "connect_set_exclusive": {
                         "type": "boolean",
                         "description": "If true with connect_set, disconnects all other servers first.",
                     },
                     "search_sets": {
                         "type": "string",
                         "description": "Search set descriptions for matching sets.",
                     },
                     "upsert_set": {
                         "type": "object",
                         "description": "Create or update a Set.",
                         "properties": {
                             "name": {"type": "string"},
                             "servers": {
                                 "type": "array",
                                 "items": {"type": "string"}
                             },
                             "description": {"type": "string"},
                             "include_sets": {
                                 "type": "array",
                                 "items": {"type": "string"},
                                 "description": "Other sets to include (composability)"
                             }
                         },
                         "required": ["name"]
                     },
                     "delete_set": {
                         "type": "string",
                         "description": "Name of the Set to delete.",
                     },
                     "disconnect": {
                         "type": "string",
                         "description": "Name of the server to disconnect (turn off).",
                     },
                     "disconnect_set": {
                        "type": "string",
                        "description": "Name of the Set to disconnect (turn off all servers in set).",
                     },
                     "disconnect_all": {
                         "type": "boolean",
                         "description": "If true, disconnects all servers.",
                     },
                     "populate_catalog": {
                         "type": "boolean",
                         "description": "If true, connects to all enabled servers, refreshes catalog cache, then disconnects. Use when adding new MCPs.",
                     },
                 },
             },
        ),
        types.Tool(
             name=TOOL_SEARCH_MCP_CATALOG,
             description="Search for tools in the offline catalog and discover Sets/Collections.",
             inputSchema={
                 "type": "object",
                 "required": ["query"],
                 "properties": {
                     "query": {
                         "type": "string",
                         "description": "Search query for tools or collections.",
                     },
                     "max_results": {
                         "type": "integer",
                         "description": "Maximum results to return. Default 20.",
                         "default": 20,
                     },
                 },
             },
        ),
        types.Tool(
            name=TOOL_EXECUTE_ACTION,
            description="Execute a specific action with the provided parameters.",
            inputSchema={
                "type": "object",
                "required": ["server_name", "action_name"],
                "properties": {
                    "server_name": {
                        "type": "string",
                        "enum": user_available_servers,
                        "description": "The name of the server",
                    },
                    "action_name": {
                        "type": "string",
                        "description": "The name of the action/operation to execute",
                    },
                    "path_params": {
                        "type": "string",
                        "description": "JSON string containing path parameters",
                    },
                    "query_params": {
                        "type": "string",
                        "description": "JSON string containing query parameters",
                    },
                    "body_schema": {
                        "type": "string",
                        "description": "JSON string containing request body",
                        "default": "{}",
                    },
                },
            },
        ),
        types.Tool(
            name=TOOL_SEARCH_DOCUMENTATION,
            description="Search for server action documentations by keyword matching.",
            inputSchema={
                "type": "object",
                "required": ["query", "server_name"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keywords",
                    },
                    "server_name": {
                        "type": "string",
                        "enum": user_available_servers,
                        "description": "Name of the server to search within.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to return. Default: 10",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 10,
                    },
                },
            },
        ),
        types.Tool(
            name=TOOL_HANDLE_AUTH_FAILURE,
            description="Handle authentication failures that occur when executing actions.",
            inputSchema={
                "type": "object",
                "required": ["server_name", "intention"],
                "properties": {
                    "server_name": {
                        "type": "string",
                        "enum": user_available_servers,
                        "description": "The name of the server",
                    },
                    "intention": {
                        "type": "string",
                        "enum": ["get_auth_url", "save_auth_data"],
                        "description": "Action to take for authentication",
                    },
                    "auth_data": {
                        "type": "object",
                        "description": "Authentication data when saving",
                    },
                },
            },
        ),
    ]


async def execute_tool(
    name: str, arguments: dict, client_manager: MCPClientManager
) -> List[types.ContentBlock]:
    """Execute a tool with the given arguments."""
    try:
        result = None

        if name == TOOL_DISCOVER_SERVER_ACTIONS:
            user_query = arguments.get("user_query")
            server_names = arguments.get("server_names")

            # If no server names provided, use all available servers
            if not server_names:
                server_names = list(client_manager.active_clients.keys())

            # Discover actions from specified servers
            discovery_result = {}
            for server_name in server_names:
                try:
                    client = client_manager.get_client(server_name)
                    tools = await client.list_tools()

                    # Filter tools based on user query if provided
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
                    discovery_result[server_name] = {
                        "error": f"Server '{server_name}' not connected. Run: manage_servers.exec {{\"connect\": \"{server_name}\"}}"
                    }
                except Exception as e:
                    logger.error(f"Error discovering tools for {server_name}: {e}")
                    discovery_result[server_name] = {"error": str(e)}

            result = discovery_result

        elif name == TOOL_MANAGE_SERVERS:
            list_configured = arguments.get("list_configured_mcps")
            list_sets = arguments.get("list_sets")
            
            connect_server = arguments.get("connect")
            connect_set = arguments.get("connect_set")
            
            upsert_set = arguments.get("upsert_set")
            delete_set = arguments.get("delete_set")
            
            disconnect_server = arguments.get("disconnect")
            disconnect_set = arguments.get("disconnect_set")
            
            disconnect_all = arguments.get("disconnect_all")

            results = []

            if list_configured:
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

            search_sets_query = arguments.get("search_sets")
            if search_sets_query:
                sets = client_manager.server_list.list_sets()
                query_lower = search_sets_query.lower()
                matches = []
                for name, data in sets.items():
                    desc = data.get('description', '')
                    if query_lower in name.lower() or query_lower in desc.lower():
                        servers = ', '.join(data.get('servers', []))
                        matches.append(f"{name}: {desc}\n  {servers}" if desc else f"{name}:\n  {servers}")
                results.append("\n".join(matches) if matches else f"no sets matching '{search_sets_query}'")

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
                    results.append(f"error: {e}")

            if delete_set:
                success = client_manager.server_list.remove_set(delete_set)
                results.append(f"set '{delete_set}' deleted" if success else f"error: set '{delete_set}' not found")

            if connect_server:
                server_config = client_manager.server_list.get_server(connect_server)
                if server_config:
                    asyncio.create_task(client_manager._connect_server(server_config))
                    results.append(f"{connect_server} starting")
                else:
                    results.append(f"error: {connect_server} not configured")
            
            if connect_set:
                servers_in_set = client_manager.server_list.get_set(connect_set)
                if servers_in_set:
                    # Exclusive mode: disconnect everything else first
                    connect_set_exclusive = arguments.get("connect_set_exclusive")
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

            if disconnect_server:
                await client_manager._disconnect_server(disconnect_server)
                results.append(f"{disconnect_server} off")

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

            populate_catalog = arguments.get("populate_catalog")
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
                            indexed.append(f"{server.name}: error - {e}")
                    results.append(f"catalog: indexed {len(to_populate)}, skipped {len(already_cached)}\n" + "\n".join(indexed))

            return [types.TextContent(type="text", text="\n".join(str(r) for r in results))]

        elif name == TOOL_SEARCH_MCP_CATALOG:
            query = arguments.get("query")
            max_results = arguments.get("max_results", 20)
            
            # Search tools
            tool_results = client_manager.catalog.search(query, max_results)
            # Annotate with current status
            active_servers = client_manager.list_active_servers()
            for r in tool_results:
                r["current_status"] = "online" if r.get("category_name") in active_servers else "offline"
            
            # Simple "Collection Search" logic: Check if query matches any Set names or descriptions
            sets = client_manager.server_list.list_sets()
            matching_sets = []
            for set_name, set_data in sets.items():
                # list_sets now returns dict with keys "description" (str) and "servers" (list)
                description = set_data.get("description", "")
                
                # BM25-ish: simple containment for now
                if (query.lower() in set_name.lower()) or (query.lower() in description.lower()):
                     matching_sets.append({
                         "type": "collection",
                         "name": set_name,
                         "description": description,
                         "servers": set_data.get("servers", []),
                         "status": "available"
                     })
            
            final_results = {"collections": matching_sets, "tools": tool_results}
            
            return [types.TextContent(type="text", text=json.dumps(final_results, indent=2))]

        elif name == TOOL_GET_ACTION_DETAILS:
            server_name = arguments.get("server_name")
            action_name = arguments.get("action_name")

            try:
                client = client_manager.get_client(server_name)
                tools = await client.list_tools()

                tool = next((t for t in tools if t["name"] == action_name), None)

                if tool:
                    result = {
                        "name": tool["name"],
                        "description": tool.get("description"),
                        "inputSchema": tool.get("inputSchema"),
                    }
                else:
                    result = {
                        "error": f"Action '{action_name}' not found on server '{server_name}'"
                    }
            except KeyError:
                result = {
                    "error": f"Server '{server_name}' not connected. Run: manage_servers.exec {{\"connect\": \"{server_name}\"}}"
                }

        elif name == TOOL_EXECUTE_ACTION:
            server_name = arguments.get("server_name")
            action_name = arguments.get("action_name")
            path_params = arguments.get("path_params")
            query_params = arguments.get("query_params")
            body_schema = arguments.get("body_schema")
            
            # Check if server is connected (no JIT - explicit connect required)
            if server_name not in client_manager.active_clients:
                server_config = client_manager.server_list.get_server(server_name)
                if server_config:
                    return [types.TextContent(type="text", text=json.dumps({
                        "error": f"Server '{server_name}' is not connected",
                        "suggestion": f"Connect first with: manage_servers.exec {{\"connect\": \"{server_name}\"}}"
                    }, indent=2))]
                else:
                    return [types.TextContent(type="text", text=json.dumps({"error": f"Server '{server_name}' not configured"}, indent=2))]


            if not server_name or not action_name:
                return [
                    types.TextContent(
                        type="text",
                        text="Error: Both server_name and action_name are required",
                    )
                ]

            try:
                # Check if server exists and is connected
                if server_name not in client_manager.active_clients:
                    available_servers = client_manager.list_active_servers()
                    result = _build_error_response(
                        f"Server '{server_name}' not found or not connected",
                        server_name=server_name,
                        available_servers=available_servers,
                        suggestion=f"Available servers: {', '.join(available_servers)}" if available_servers else "No servers connected"
                    )
                else:
                    client = client_manager.get_client(server_name)

                    # Check connection status
                    if not client.is_connected():
                        result = _build_error_response(
                            f"Server '{server_name}' is not connected",
                            server_name=server_name,
                            suggestion="Try reconnecting the server or check its configuration"
                        )
                    else:
                        action_params = {}

                        # Parse parameters if they're JSON strings
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
                                except json.JSONDecodeError as json_err:
                                    result = _build_error_response(
                                        f"Invalid JSON in {param_name}: {str(json_err)}",
                                        param_name=param_name,
                                        param_value=param_value[:100] if isinstance(param_value, str) else str(param_value)[:100]
                                    )
                                    break
                        else:
                            # All parameters parsed successfully - call the tool
                            try:
                                return await client.call_tool(action_name, action_params)
                            except RuntimeError as runtime_err:
                                # MCP SDK errors (tool execution failures, connection issues)
                                logger.error(f"MCP tool execution error: {str(runtime_err)}")
                                logger.error(f"Traceback: {traceback.format_exc()}")
                                result = _build_error_response(
                                    f"Tool '{action_name}' execution failed: {str(runtime_err)}",
                                    traceback.format_exc(),
                                    server_name=server_name,
                                    action_name=action_name,
                                    suggestion="Check tool parameters and server logs"
                                )
                            except Exception as tool_err:
                                # Unexpected errors during tool execution
                                logger.error(f"Unexpected error calling tool: {str(tool_err)}")
                                logger.error(f"Traceback: {traceback.format_exc()}")
                                result = _build_error_response(
                                    f"Unexpected error executing '{action_name}': {str(tool_err)}",
                                    traceback.format_exc(),
                                    server_name=server_name,
                                    action_name=action_name
                                )

            except Exception as e:
                # Top-level unexpected errors
                logger.exception(f"Unexpected error in execute_action: {e}")
                result = _build_error_response(
                    f"Internal error: {str(e)}",
                    traceback.format_exc(),
                    server_name=server_name,
                    action_name=action_name
                )

        elif name == TOOL_SEARCH_DOCUMENTATION:
            query = arguments.get("query")
            server_name = arguments.get("server_name")
            max_results = arguments.get("max_results", 10)

            if not query or not server_name:
                return [
                    types.TextContent(
                        type="text",
                        text="Error: Both query and server_name are required",
                    )
                ]

            try:
                client = client_manager.get_client(server_name)
                tools = await client.list_tools()

                tools_map = {server_name: tools if tools else []}
                searcher = UniversalToolSearcher(tools_map)
                result = searcher.search(query, max_results=max_results)
            except KeyError:
                result = [
                    {"error": f"Server '{server_name}' not connected. Run: manage_servers.exec {{\"connect\": \"{server_name}\"}}"}
                ]
            except Exception as e:
                logger.error(f"Error searching documentation: {str(e)}")
                result = [{"error": f"Error searching documentation: {str(e)}"}]

        elif name == TOOL_HANDLE_AUTH_FAILURE:
            server_name = arguments.get("server_name")
            intention = arguments.get("intention")
            auth_data = arguments.get("auth_data")

            if not server_name or not intention:
                return [
                    types.TextContent(
                        type="text",
                        text="Error: Both server_name and intention are required",
                    )
                ]

            try:
                if intention == "get_auth_url":
                    result = {
                        "server": server_name,
                        "message": f"Authentication required for server '{server_name}'",
                        "instructions": "Please provide authentication credentials",
                        "required_fields": {"token": "Authentication token or API key"},
                    }
                elif intention == "save_auth_data":
                    if not auth_data:
                        return [
                            types.TextContent(
                                type="text",
                                text="Error: auth_data is required when intention is 'save_auth_data'",
                            )
                        ]
                    result = {
                        "server": server_name,
                        "status": "success",
                        "message": f"Authentication data saved for server '{server_name}'",
                    }
                else:
                    result = {"error": f"Invalid intention: '{intention}'"}
            except Exception as e:
                logger.error(f"Error handling auth failure: {str(e)}")
                result = {"error": f"Error handling auth failure: {str(e)}"}

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

        # Convert result to TextContent
        return [
            types.TextContent(
                type="text",
                text=(
                    json.dumps(result, separators=(",", ":"))
                    if isinstance(result, (dict, list))
                    else str(result)
                ),
            )
        ]

    except Exception as e:
        logger.exception(f"Error executing tool {name}: {e}")
        return [
            types.TextContent(
                type="text", text=f"Error executing tool '{name}': {str(e)}"
            )
        ]
