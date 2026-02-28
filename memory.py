"""
🧠 Memory Module — The Agent's Brain
======================================
This manages the conversation history (messages list).

WHY IS THIS NEEDED?
LLMs are stateless — they don't remember previous calls.
Every time you call the API, you must send the ENTIRE conversation.
This module manages that growing list of messages.

KEY CONCEPT: Message Roles
  - "system"    → Instructions for the LLM (personality, rules)
  - "user"      → What the human said
  - "assistant" → What the LLM responded
  - "tool"      → Results from tool calls (fed back to the LLM)
"""


class ConversationMemory:
    """Manages conversation history for the agent."""

    def __init__(self, system_prompt: str):
        """
        Initialize memory with a system prompt.

        The system prompt defines WHO the agent is and HOW it should behave.
        This is the most important message — it shapes everything the agent does.
        """
        self.system_prompt = system_prompt
        self.messages: list[dict] = [
            {"role": "system", "content": system_prompt}
        ]

    def add_user_message(self, content: str):
        """Add a message from the user."""
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, message):
        """
        Add the assistant's response (could contain text AND/OR tool calls).

        We store the full message object from the API response because
        it may contain tool_calls that we need to reference later.
        """
        self.messages.append(message)

    def add_tool_result(self, tool_call_id: str, result: str):
        """
        Add the result of a tool call.

        IMPORTANT: The tool_call_id links this result back to the specific
        tool call the LLM made. Without it, the LLM wouldn't know which
        tool this result belongs to.
        """
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result
        })

    def get_messages(self) -> list[dict]:
        """Return the full conversation history for the API call."""
        return self.messages

    def get_message_count(self) -> int:
        """How many messages are in the conversation."""
        return len(self.messages)

    def clear(self):
        """Reset the conversation, keeping only the system prompt."""
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        print("🧹 Memory cleared! Starting fresh.")

    def __repr__(self):
        return f"ConversationMemory({self.get_message_count()} messages)"
