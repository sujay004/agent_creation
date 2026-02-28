# 🤖 Research Assistant Agent

A Python AI agent that can reason, use tools, and help you research topics — built from scratch to learn how agents work.

## What This Project Teaches

- **OpenAI SDK** — How to talk to LLMs from Python
- **Tool/Function Calling** — Letting the LLM decide which tools to use
- **Agent Loop (ReAct)** — The Reason → Act → Observe pattern
- **Conversation Memory** — Managing context across messages

## Quick Start

```bash
# 1. Activate the virtual environment
source venv/bin/activate

# 2. Add your OpenAI API key to .env
#    Edit .env and replace 'sk-your-key-here' with your actual key

# 3. Run the agent
python agent.py
```

## Project Structure

```
agent_creation/
├── agent.py          # 🧠 Main agent with the ReAct reasoning loop
├── tools.py          # 🔧 Tool definitions + schemas for the LLM
├── memory.py         # 💾 Conversation memory manager
├── .env              # 🔑 API keys (never commit this!)
├── .gitignore        # 🚫 Files to exclude from git
├── requirements.txt  # 📦 Python dependencies
└── README.md         # 📖 You are here!
```

## Available Tools

| Tool | What It Does |
|------|-------------|
| `calculator` | Evaluate math expressions |
| `read_webpage` | Fetch and read web page content |
| `save_note` | Save important findings |
| `get_notes` | Retrieve all saved notes |

## Example Conversations

```
👤 You: What is 15% of 2847?
🤖 Agent: [uses calculator] 15% of 2847 is 427.05

👤 You: Read the Python homepage and summarize what Python is
🤖 Agent: [reads webpage] Python is a programming language that...

👤 You: Save that as a note for later
🤖 Agent: [saves note] ✅ Note saved!
```

## How the Agent Loop Works

```
User Question
     │
     ▼
┌─────────────────┐
│  LLM Thinks     │◄──────────────┐
│  (with tools    │               │
│   available)    │               │
└────────┬────────┘               │
         │                        │
    ┌────▼────┐                   │
    │ Tool    │── YES ──► Execute │
    │ Call?   │          Tool     │
    └────┬────┘          │       │
         │               │       │
         NO              Result ─┘
         │
         ▼
   Final Answer
```

## Next Steps

- [ ] Add a web search tool (DuckDuckGo API)
- [ ] Add streaming responses
- [ ] Add logging for debugging
- [ ] Try more complex multi-step research tasks
