"""
🤖 MCP-Powered Task Manager Agent
====================================
This agent is like agent.py BUT instead of using hardcoded
tools from tools.py, it DISCOVERS tools dynamically from
the MCP server at runtime.

KEY DIFFERENCE from agent.py:
  agent.py:          tools are hardcoded in tools.py
  mcp_agent.py:      tools are fetched from MCP server at startup

This means if you add a new tool to server.py,
this agent automatically gets it — NO code changes needed here!

HOW IT FLOWS:
1. Start → connect to MCP server → ask "what tools do you have?"
2. Get tool schemas → convert to OpenAI format
3. Run the same ReAct loop as agent.py
4. When LLM calls a tool → route it TO the MCP server
5. Get result → feed back to LLM → continue loop
"""

import os
import json
import sys
import subprocess
import threading
import time
import asyncio
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from memory import ConversationMemory

# ── MCP imports
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

load_dotenv()

# ─────────────────────────────────────────────
# Gemini client (same as agent.py)
# ─────────────────────────────────────────────
client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

SERVER_SCRIPT = str(Path(__file__).parent / "mcp_server" / "server.py")
MAX_ITERATIONS = 10

SYSTEM_PROMPT = """You are a helpful Task Manager assistant.
You help users manage their tasks and to-do lists.

You have tools to:
- Add new tasks (with optional priority and due date)
- List tasks (filter by status or priority)
- Mark tasks as complete
- Delete tasks
- Get a summary of all tasks

Always confirm actions clearly and show task details when relevant.
When listing tasks, display them in a readable format.
When a user says things like "add a task", "what tasks do I have",
"mark X as done", "show my tasks", use the appropriate tools."""


# ─────────────────────────────────────────────
# MCP Connection (async core)
# ─────────────────────────────────────────────

class MCPTaskAgent:
    """
    Agent that uses MCP for its tools.

    This runs the MCP client connection in a background
    async event loop and exposes a simple synchronous API.
    """

    def __init__(self):
        self.tool_schemas = []      # OpenAI-format schemas discovered from MCP
        self.session = None         # MCP session
        self._loop = None
        self._connected = False

    def connect(self):
        """Start MCP server subprocess and discover tools."""
        print("🔌 Connecting to MCP Task Manager server...")

        # We run the async MCP client in a background thread
        ready_event = threading.Event()
        self._loop = asyncio.new_event_loop()

        def run():
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._run_session(ready_event))

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        ready_event.wait(timeout=10)

        if self._connected:
            print(f"✅ MCP connected! {len(self.tool_schemas)} tools loaded: "
                  f"{[t['function']['name'] for t in self.tool_schemas]}")
        else:
            print("❌ Failed to connect to MCP server.")
            sys.exit(1)

    async def _run_session(self, ready_event: threading.Event):
        """The async MCP session that runs in the background."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[SERVER_SCRIPT],
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                self.session = session
                await session.initialize()

                # Discover tools from server
                tools_result = await session.list_tools()

                # Convert MCP tool format → OpenAI function calling format
                self.tool_schemas = [
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description or "",
                            "parameters": t.inputSchema,
                        }
                    }
                    for t in tools_result.tools
                ]

                self._connected = True
                ready_event.set()  # Signal that we're ready

                # Keep the session alive until agent shuts down
                await self._keep_alive()

    async def _keep_alive(self):
        """Keep the background session alive."""
        while self._connected:
            await asyncio.sleep(0.1)

    def call_mcp_tool(self, tool_name: str, tool_args: dict) -> str:
        """Call a tool on the MCP server (synchronous wrapper)."""
        future = asyncio.run_coroutine_threadsafe(
            self.session.call_tool(tool_name, tool_args),
            self._loop
        )
        result = future.result(timeout=15)
        return "\n".join(
            c.text for c in result.content if hasattr(c, "text")
        )

    def disconnect(self):
        self._connected = False


# ─────────────────────────────────────────────
# The Agent Loop (same ReAct pattern as agent.py)
# ─────────────────────────────────────────────

def run_mcp_agent(user_input: str, memory: ConversationMemory, mcp: MCPTaskAgent) -> str:
    """
    Same ReAct loop as agent.py, but tools come from MCP server.

    The only difference: instead of TOOL_FUNCTIONS[name](args),
    we call mcp.call_mcp_tool(name, args).
    """
    memory.add_user_message(user_input)

    for iteration in range(MAX_ITERATIONS):
        print(f"\n🔄 Thinking... (iteration {iteration + 1})")

        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=memory.get_messages(),
            tools=mcp.tool_schemas,   # ← Tools from MCP, not hardcoded!
            tool_choice="auto",
        )

        assistant_message = response.choices[0].message
        memory.add_assistant_message(assistant_message.to_dict())

        if assistant_message.tool_calls:
            print(f"🔧 Calling {len(assistant_message.tool_calls)} MCP tool(s)")
            for tool_call in assistant_message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                print(f"   → {name}({args})")

                # Route to MCP server instead of local function
                result = mcp.call_mcp_tool(name, args)
                print(f"   ← {result[:80]}...")

                memory.add_tool_result(tool_call.id, result)
            continue

        print(f"\n✅ Done in {iteration + 1} iteration(s)")
        return assistant_message.content

    return "⚠️ Reached max iterations."


def main():
    print("=" * 60)
    print("🤖 MCP Task Manager Agent")
    print("=" * 60)

    # Connect to MCP server and load tools
    mcp = MCPTaskAgent()
    mcp.connect()

    memory = ConversationMemory(SYSTEM_PROMPT)
    print("\nReady! Ask me to manage your tasks. Type 'quit' to exit.\n")

    while True:
        user_input = input("\n👤 You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            mcp.disconnect()
            print("\n👋 Goodbye!")
            break
        if user_input.lower() == "clear":
            memory.clear()
            continue
        if not user_input:
            continue

        try:
            response = run_mcp_agent(user_input, memory, mcp)
            print(f"\n🤖 Agent: {response}")
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
