"""
🔌 MCP Client Bridge — Connecting Agent to MCP Server
=======================================================
This module is the BRIDGE between your agent and the MCP server.
It does two important things:

1. TOOL DISCOVERY:
   Starts the MCP server as a subprocess and asks it:
   "What tools do you have?" → converts them into OpenAI-compatible
   tool schemas that your agent already understands.

2. TOOL EXECUTION:
   When the LLM decides to call an MCP tool, this module sends
   the request to the MCP server and gets the result back.

WHY A SUBPROCESS?
MCP uses stdio transport — the server and client talk through
stdin/stdout pipes. We launch the server as a child process
and communicate with it over those pipes.

FLOW:
  agent.py
    │ "which tools available?"
    ▼
  mcp_client.py ──(subprocess)──► mcp_server/server.py
    │                ◄── tool schemas ──┘
    │ (converts to OpenAI format)
    ▼
  agent.py uses tools normally
"""

import asyncio
import sys
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


# Path to the MCP server script
SERVER_SCRIPT = str(Path(__file__).parent / "mcp_server" / "server.py")


async def _get_tools_and_run(user_input_queue, result_queue):
    """
    Internal async function that:
    1. Starts the MCP server subprocess
    2. Fetches available tools
    3. Handles tool call requests
    """
    server_params = StdioServerParameters(
        command=sys.executable,         # Use the same Python interpreter
        args=[SERVER_SCRIPT],           # Run our server.py
        env=None,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Step 1: Initialize the MCP connection (handshake)
            await session.initialize()

            # Step 2: Discover tools the server offers
            tools_response = await session.list_tools()
            await result_queue.put(("tools", tools_response.tools))

            # Step 3: Wait for tool call requests from the agent
            while True:
                request = await user_input_queue.get()
                if request is None:
                    break  # Shutdown signal

                tool_name, tool_args = request
                response = await session.call_tool(tool_name, tool_args)

                # Extract text from response
                text = "\n".join(
                    c.text for c in response.content
                    if hasattr(c, "text")
                )
                await result_queue.put(("result", text))


class MCPClient:
    """
    Synchronous wrapper around the async MCP client.

    Your agent.py runs synchronously (no async/await).
    This class hides all the async complexity and gives
    you a simple, clean interface to use.
    """

    def __init__(self):
        self._tools: list = []
        self._loop = asyncio.new_event_loop()
        self._input_queue = asyncio.Queue()
        self._result_queue = asyncio.Queue()
        self._task = None

    def connect(self):
        """Start the MCP server and discover its tools."""
        import threading

        def run_loop():
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(
                _get_tools_and_run(self._input_queue, self._result_queue)
            )

        # Run the async MCP client in a background thread
        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()

        # Wait for tools to be returned
        msg_type, data = self._loop.run_until_complete(
            self._result_queue.get()
        ) if False else self._sync_get()

        if msg_type == "tools":
            self._tools = data
            print(f"🔌 MCP Server connected! Found {len(self._tools)} tools.")

    def _sync_get(self):
        """Get next result from the queue (blocking)."""
        import concurrent.futures
        future = concurrent.futures.Future()

        async def _get():
            item = await self._result_queue.get()
            future.set_result(item)

        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(_get(), loop=self._loop)
        )
        return future.result(timeout=10)

    def get_openai_tool_schemas(self) -> list[dict]:
        """
        Convert MCP tool definitions → OpenAI function calling format.

        This is the KEY translation layer. MCP and OpenAI use slightly
        different formats for tool schemas, so we convert between them.
        """
        schemas = []
        for tool in self._tools:
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                }
            })
        return schemas

    def call_tool(self, tool_name: str, tool_args: dict) -> str:
        """Call a tool on the MCP server and return the text result."""
        async def _send_and_get():
            await self._input_queue.put((tool_name, tool_args))
            return await self._result_queue.get()

        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(
                self._input_queue.put((tool_name, tool_args)),
                loop=self._loop
            )
        )
        msg_type, data = self._sync_get()
        return data

    def disconnect(self):
        """Cleanly shut down the MCP server connection."""
        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(
                self._input_queue.put(None),
                loop=self._loop
            )
        )
