"""
🚀 MCP Task Manager Server
============================
This is your first MCP server! It exposes task management
tools that any MCP-compatible client (your agent, Claude,
Cursor, etc.) can discover and use.

HOW MCP WORKS:
1. Server starts and registers its tools
2. Client connects and asks "what tools do you have?"
3. Server responds with tool schemas (name, description, args)
4. Client (LLM) decides when to call a tool
5. Client sends a tool call request
6. Server executes it and returns the result

The transport here is "stdio" — meaning the server and client
talk to each other through standard input/output (like a pipe).
This is the simplest way to connect an MCP server.
"""

import json
import sys
import asyncio
import requests
import urllib.parse
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

import storage  # Our storage module

# ─────────────────────────────────────────────
# Create the MCP Server instance
# ─────────────────────────────────────────────
# Think of this as Flask's `app = Flask(__name__)`
# but for MCP. We give it a name that clients will see.
app = Server("task-manager")


# ─────────────────────────────────────────────
# Register: What tools does this server expose?
# ─────────────────────────────────────────────
# This is what the client calls when it wants to know
# "hey server, what can you do?"
@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="add_task",
            description="Add a new task to the task list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title":    {"type": "string",  "description": "The task description"},
                    "priority": {"type": "string",  "description": "'high', 'medium', or 'low'", "default": "medium"},
                    "due_date": {"type": "string",  "description": "Optional due date in YYYY-MM-DD format"},
                },
                "required": ["title"],
            },
        ),
        types.Tool(
            name="list_tasks",
            description="List all tasks, optionally filtered by status or priority.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status":   {"type": "string", "description": "Filter by 'pending' or 'done'. Omit for all."},
                    "priority": {"type": "string", "description": "Filter by 'high', 'medium', or 'low'. Omit for all."},
                },
            },
        ),
        types.Tool(
            name="complete_task",
            description="Mark a task as completed using its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The task ID to mark as done"},
                },
                "required": ["task_id"],
            },
        ),
        types.Tool(
            name="delete_task",
            description="Delete a task permanently using its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The task ID to delete"},
                },
                "required": ["task_id"],
            },
        ),
        types.Tool(
            name="get_summary",
            description="Get a summary of all tasks: total, pending, done, overdue, and high priority counts.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="get_random_joke",
            description="Fetch a random programming or general joke from a free external API. Use this to lighten the mood!",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="get_wikipedia_summary",
            description="Get a short summary of a topic from Wikipedia.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The topic to search for on Wikipedia (e.g. 'Python (programming language)')."}
                },
                "required": ["topic"],
            },
        ),
    ]


# ─────────────────────────────────────────────
# Handle: Execute a tool when the client asks
# ─────────────────────────────────────────────
# This is the router. When the client says "call add_task",
# this function receives the request, dispatches to storage.py,
# and returns the result back to the client.
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Execute the requested tool and return results as text."""

    if name == "add_task":
        task = storage.add_task(
            title=arguments["title"],
            priority=arguments.get("priority", "medium"),
            due_date=arguments.get("due_date"),
        )
        result = f"✅ Task added!\n" \
                 f"  ID:       {task['id']}\n" \
                 f"  Title:    {task['title']}\n" \
                 f"  Priority: {task['priority']}\n" \
                 f"  Due:      {task.get('due_date', 'No due date')}"

    elif name == "list_tasks":
        tasks = storage.list_tasks(
            status=arguments.get("status"),
            priority=arguments.get("priority"),
        )
        if not tasks:
            result = "📭 No tasks found matching your criteria."
        else:
            lines = ["📋 Tasks:\n"]
            for t in tasks:
                status_icon = "✅" if t["status"] == "done" else "⏳"
                priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t["priority"], "⚪")
                due = f" | Due: {t['due_date']}" if t.get("due_date") else ""
                lines.append(f"{status_icon} [{t['id']}] {priority_icon} {t['title']}{due}")
            result = "\n".join(lines)

    elif name == "complete_task":
        task = storage.complete_task(arguments["task_id"])
        if task:
            result = f"✅ Task '{task['title']}' marked as done!"
        else:
            result = f"❌ No task found with ID: {arguments['task_id']}"

    elif name == "delete_task":
        deleted = storage.delete_task(arguments["task_id"])
        if deleted:
            result = f"🗑️ Task {arguments['task_id']} deleted."
        else:
            result = f"❌ No task found with ID: {arguments['task_id']}"

    elif name == "get_summary":
        summary = storage.get_summary()
        result = (
            f"📊 Task Summary:\n"
            f"  Total:         {summary['total']}\n"
            f"  Pending:       {summary['pending']}\n"
            f"  Done:          {summary['done']}\n"
            f"  Overdue:       {summary['overdue']}\n"
            f"  High Priority: {summary['high_priority_pending']}"
        )

    elif name == "get_random_joke":
        try:
            url = "https://official-joke-api.appspot.com/random_joke"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            response.raise_for_status()
            data = response.json()
            result = f"🤣 Joke:\n{data['setup']}\n... {data['punchline']}"
        except Exception as e:
            result = f"❌ Error fetching joke: {str(e)}"

    elif name == "get_wikipedia_summary":
        topic = arguments["topic"]
        try:
            url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exsentences=3&exlimit=1&titles={urllib.parse.quote(topic)}&explaintext=1&format=json"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            response.raise_for_status()
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            page = list(pages.values())[0]
            if "extract" in page:
                result = f"� Wikipedia Summary for {topic}:\n{page['extract']}"
            else:
                result = f"❌ No Wikipedia page found for '{topic}'."
        except Exception as e:
            result = f"❌ Error fetching Wikipedia summary for {topic}: {str(e)}"

    else:
        result = f"❌ Unknown tool: {name}"

    # MCP expects results as a list of TextContent objects
    return [types.TextContent(type="text", text=result)]


# ─────────────────────────────────────────────
# Start the server using stdio transport
# ─────────────────────────────────────────────
# stdio = talk via stdin/stdout (pipes)
# This is the standard way MCP servers run locally.
async def main():
    print("🚀 Task Manager MCP Server starting...", file=sys.stderr, flush=True)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
