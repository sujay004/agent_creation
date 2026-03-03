# 🤖 Python AI Agent — Complete Flow Documentation

A reference guide for everything in this project. Use this to understand how the pieces fit together.

---

## 📂 1. Full Project Map

```text
agent_creation/
│
├── 🤖 CORE AGENT (Original)
│   ├── agent.py       # Main agent loop + interactive chat
│   ├── memory.py      # Conversation history manager
│   └── tools.py       # Hardcoded tools (calculator, web reader, notes)
│
├── 🔌 MCP AGENT (New - Protocol-based)
│   ├── mcp_agent.py   # MCP-powered agent loop
│   ├── mcp_client.py  # Async bridge to MCP server
│   └── mcp_server/
│       ├── server.py  # MCP server (exposes tools over stdio)
│       ├── storage.py # Task persistence (reads/writes tasks.json)
│       └── tasks.json # Task data file (auto-created)
│
├── ⚙️  CONFIG
│   ├── .env           # API keys (GEMINI_API_KEY)
│   ├── requirements.txt
│   └── .gitignore
```

---

## 🌊 2. Original Agent Flow (`agent.py`)

This is the **ReAct pattern** — Reason → Act → Observe → Repeat.

```
python agent.py
       │
       ▼
   main()                    ← entry point (if __name__ == "__main__")
       │
       ▼
   ┌─────────────────────────────────────────┐
   │           while True: (chat loop)       │
   │                                         │
   │  input("👤 You: ") ◄── your keyboard    │
   │       │                                 │
   │       ▼                                 │
   │  run_agent(user_input, memory)          │
   │       │                                 │
   │       └──────────────────────────────►  │
   │                                         │
   │  print("🤖 Agent:", response)           │
   └─────────────────────────────────────────┘
```

### Inside `run_agent()` — the ReAct Loop:

```
user types: "What is 25% of 1280?"
               │
               ▼
  memory.add_user_message(user_input)      ← log user turn
               │
               ▼
  ┌────────────────────────────────────┐
  │   for iteration in range(10):      │
  │                                    │
  │   Gemini API call                  │ ← LLM reads full history
  │   ┌──────────────────────────┐     │
  │   │  REASON                  │     │ ← "I need to calculate..."
  │   │  decides to use a tool   │     │
  │   └──────────────────────────┘     │
  │              │                     │
  │    Has tool calls?                 │
  │    YES ──────▼                     │
  │   ┌──────────────────────────┐     │
  │   │  ACT                     │     │
  │   │  calculator('0.25*1280') │     │ ← runs Python function
  │   │  result = 320.0          │     │
  │   └──────────────────────────┘     │
  │              │                     │
  │   memory.add_tool_result(...)      │ ← log tool result
  │              │                     │
  │    NO (no more tool calls)         │
  │    ──────────▼                     │
  │   ┌──────────────────────────┐     │
  │   │  OBSERVE + ANSWER        │     │
  │   │  "25% of 1280 is 320"    │     │
  │   └──────────────────────────┘     │
  │              │                     │
  │         return answer              │
  └────────────────────────────────────┘
```

---

## 🧠 3. Memory Flow (`memory.py`)

LLMs are **stateless** — they forget everything between calls. `memory.py` gives the agent "short-term memory" by keeping the full conversation history.

```
ConversationMemory object (lives in RAM while agent runs)
├── messages: [
│     { role: "system",    content: "You are a helpful..." }   ← set on startup
│     { role: "user",      content: "What is 25%..." }         ← add_user_message()
│     { role: "assistant", content: "(thinking...)" }          ← add_assistant_message()
│     { role: "tool",      content: "320.0" }                  ← add_tool_result()
│     { role: "user",      content: "Now what is 50%..." }     ← next user turn
│     ...
│   ]

Methods:
  .add_user_message(text)           →  appends { role: "user", content: text }
  .add_assistant_message(msg)       →  appends { role: "assistant", ... }
  .add_tool_result(call_id, result) →  appends { role: "tool", content: result }
  .get_messages()                   →  returns the full list (sent to Gemini each call)
  .clear()                          →  wipes history (keeps system prompt)
```

**Why this matters:** Every API call sends the ENTIRE `.get_messages()` list. That's why the LLM knows what you asked 3 messages ago.

---

## 🔧 4. Tools Flow (`tools.py`)

Tools give the agent the ability to **do real things** in the world.

Each tool needs **two parts**:

### Part 1 — The Schema (what the LLM sees as JSON)
```python
{
  "type": "function",
  "function": {
    "name": "calculator",
    "description": "Evaluate a mathematical expression...",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": { "type": "string", "description": "e.g. '2 + 2'" }
      },
      "required": ["expression"]
    }
  }
}
```
The LLM reads this to know: "Oh, I can call `calculator` and pass it an `expression` string."

### Part 2 — The Python Function (what actually runs)
```python
def calculator(expression: str) -> str:
    result = eval(expression)
    return str(result)
```

### How they connect:
```
tools.py
├── TOOL_SCHEMAS   → sent to Gemini in every API call
│                    (LLM reads these, decides when/how to call a tool)
│
└── TOOL_FUNCTIONS → dict that maps name → Python function
                     agent.py uses this to actually run the function
```

### The 4 Tools:
| Tool | What it does | Key library |
|------|-------------|-------------|
| `calculator` | Evaluates math expressions | Python built-in `eval()` |
| `read_webpage` | Fetches URL, strips HTML, returns text | `requests` + `BeautifulSoup` |
| `save_note` | Appends to an in-memory list | Python list |
| `get_notes` | Returns all saved notes | Python list |

> ⚠️ **The web tool CAN'T search.** It needs a full URL. It doesn't know which sites are relevant — the LLM guesses URLs from its training data.

---

## 🔌 5. MCP Flow (`mcp_agent.py` + `mcp_server/`)

### What changes vs. the original agent?

| Feature | Original (`agent.py`) | MCP (`mcp_agent.py`) |
|---|---|---|
| Tool source | Hardcoded in `tools.py` | Fetched from `mcp_server/server.py` at startup |
| Add a new tool | Edit `tools.py` + `agent.py` | Only edit `server.py` — agent auto-discovers it |
| Tool availability | Only this project | Any MCP client (Claude, Cursor, etc.) |

### MCP Startup & Tool Discovery:
```
python mcp_agent.py
       │
       ▼
  MCPTaskAgent.connect()
       │
       ├── Spawns `mcp_server/server.py` as a subprocess
       │
       │   mcp_agent.py          server.py
       │         │    "initialize"  │
       │         │ ──────────────►  │
       │         │    "ready"       │
       │         │ ◄──────────────  │
       │         │   "list_tools"   │
       │         │ ──────────────►  │
       │         │  5 tool schemas  │
       │         │ ◄──────────────  │
       │
       └── Converts MCP schemas → OpenAI schemas
           Stores in self.tool_schemas

  Prints: "✅ MCP connected! 5 tools loaded"
```

### MCP Tool Execution (when LLM calls a tool):
```
LLM says: "Call add_task with title='Learn Python'"
               │
               ▼
  mcp_agent.py: mcp.call_mcp_tool("add_task", {"title": "Learn Python"})
               │
               ▼       stdio pipe
  mcp_client.py ────────────────► mcp_server/server.py
                                         │
                                         ▼   @app.call_tool()
                                   storage.add_task("Learn Python")
                                         │
                                         ▼
                                   tasks.json updated ✅
                                         │
                                   returns: "Task added! ID: abc123"
                                         │
               ◄──────────────────────────
               │
   result fed back to LLM context
               │
               ▼
  LLM says: "I've added the task 'Learn Python' for you!"
```

### Full MCP Sequence Diagram:
```
User     mcp_agent.py    Gemini API    mcp_client.py    server.py    tasks.json
 │             │               │              │               │            │
 │  "Add task" │               │              │               │            │
 │────────────►│               │              │               │            │
 │             │ API call +    │              │               │            │
 │             │ tool_schemas  │              │               │            │
 │             │──────────────►│              │               │            │
 │             │ "call add_task│              │               │            │
 │             │ with title=X" │              │               │            │
 │             │◄──────────────│              │               │            │
 │             │  call_mcp_tool│              │               │            │
 │             │──────────────────────────────►              │            │
 │             │               │  stdio JSON RPC             │            │
 │             │               │──────────────────────────────►           │
 │             │               │              │    add_task() │            │
 │             │               │              │───────────────────────────►│
 │             │               │              │               │            │ writes
 │             │               │              │◄───────────────────────────│
 │             │               │   "Task added!"              │            │
 │             │◄─────────────────────────────│               │            │
 │             │ API call +    │              │               │            │
 │             │ tool result   │              │               │            │
 │             │──────────────►│              │               │            │
 │             │  "I added it" │              │               │            │
 │             │◄──────────────│              │               │            │
 │  "I've added│               │              │               │            │
 │  the task!" │               │              │               │            │
 │◄────────────│               │              │               │            │
```

---

## 🔑 6. Key Concepts Summary

| Concept | In This Project |
|---|---|
| **LLM** | Gemini 2.5-flash, called via Gemini's OpenAI-compatible API |
| **ReAct Pattern** | The agent loop: Reason → call Tool → Observe result → Repeat |
| **Stateless LLM** | LLM forgets everything — solved by `memory.py` sending full history each call |
| **Tool Calling** | LLM returns structured JSON saying "call this function with these args" |
| **MCP Protocol** | Standard JSON-RPC over stdio — lets tools live in separate servers |
| **stdio Transport** | Server and client talk over stdin/stdout pipes (like a telephone wire) |
| **Tool Discovery** | MCP client asks server at startup: "what can you do?" |
| **OpenAI SDK** | Used for all LLM calls — works with OpenAI, Gemini, and Ollama by changing `base_url` |

---

## 🚀 7. How to Run

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2a. Run the original agent (hardcoded tools)
python agent.py

# 2b. Run the MCP task manager agent
python mcp_agent.py
```

> Note: `mcp_agent.py` automatically starts and manages the MCP server subprocess.
> You don't need to start the server separately.
