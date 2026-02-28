"""
🔧 Tools Module — The Agent's Hands
=====================================
Tools are functions the agent can call to interact with the real world.
Each tool needs TWO things:
  1. A SCHEMA (JSON) — tells the LLM what the tool does and what args it needs
  2. A FUNCTION — the actual Python code that runs when the tool is called

The LLM reads the schema, decides which tool to use, and generates the arguments.
Your code then calls the actual function with those arguments.
"""

import requests
from bs4 import BeautifulSoup


# ─────────────────────────────────────────────
# TOOL 1: Calculator
# ─────────────────────────────────────────────
# Why? Demonstrates the simplest possible tool.
# LLMs are bad at math — this offloads it to Python.

def calculator(expression: str) -> str:
    """Safely evaluate a math expression and return the result."""
    try:
        # Only allow safe math operations
        allowed_chars = set("0123456789+-*/.() ")
        if not all(c in allowed_chars for c in expression):
            return f"Error: Invalid characters in expression '{expression}'"

        result = eval(expression)  # Safe because we filtered chars above
        return str(result)
    except Exception as e:
        return f"Error evaluating '{expression}': {str(e)}"


# ─────────────────────────────────────────────
# TOOL 2: Web Page Reader
# ─────────────────────────────────────────────
# Why? Agents often need to read web pages to gather information.
# This fetches a URL and extracts the main text content.

def read_webpage(url: str) -> str:
    """Fetch a webpage and extract its text content."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Get text and clean it up
        text = soup.get_text(separator="\n", strip=True)

        # Limit length to avoid blowing up the context window
        if len(text) > 3000:
            text = text[:3000] + "\n\n... [Content truncated at 3000 chars]"

        return text
    except requests.RequestException as e:
        return f"Error fetching '{url}': {str(e)}"


# ─────────────────────────────────────────────
# TOOL 3: Note Taker
# ─────────────────────────────────────────────
# Why? Agents need persistent memory across steps.
# This lets the agent save important findings.

_notes: list[str] = []


def save_note(note: str) -> str:
    """Save a note for later reference."""
    _notes.append(note)
    return f"✅ Note saved! ({len(_notes)} total notes)"


def get_notes() -> str:
    """Retrieve all saved notes."""
    if not _notes:
        return "No notes saved yet."
    return "\n".join(f"📝 {i+1}. {note}" for i, note in enumerate(_notes))


# ─────────────────────────────────────────────
# TOOL SCHEMAS — What the LLM sees
# ─────────────────────────────────────────────
# These JSON schemas tell the LLM:
#   - What each tool does (description)
#   - What parameters it needs (properties)
#   - Which parameters are required

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a mathematical expression. Use this for any math calculations. "
                           "Supports: +, -, *, /, parentheses, and decimal numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The math expression to evaluate, e.g. '(12 * 3) + 7'"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "Fetch and read the text content of a webpage given its URL. "
                           "Use this to research topics, read articles, or gather information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL of the webpage to read, e.g. 'https://example.com'"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Save an important piece of information as a note for later reference. "
                           "Use this to remember key findings during research.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note": {
                        "type": "string",
                        "description": "The note content to save"
                    }
                },
                "required": ["note"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_notes",
            "description": "Retrieve all previously saved notes. Use this to review what you've learned so far.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
]


# ─────────────────────────────────────────────
# TOOL DISPATCHER — Routes LLM decisions to code
# ─────────────────────────────────────────────
# Maps tool names to their actual Python functions.
# When the LLM says "call calculator with '2+2'",
# this is how we know which function to run.

TOOL_FUNCTIONS = {
    "calculator": lambda args: calculator(args["expression"]),
    "read_webpage": lambda args: read_webpage(args["url"]),
    "save_note": lambda args: save_note(args["note"]),
    "get_notes": lambda args: get_notes(),
}
