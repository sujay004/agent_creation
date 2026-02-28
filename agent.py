"""
🤖 Agent Module — The Brain + Loop
====================================
This is the HEART of your agent. It ties everything together:
  1. Takes user input
  2. Sends it to the LLM along with available tools
  3. If the LLM wants to call a tool → execute it → feed result back
  4. Repeat until the LLM gives a final text answer

This is called the "ReAct" pattern:
  Reason → Act → Observe → Reason → Act → ... → Answer

THE KEY INSIGHT:
  The LLM doesn't execute tools itself. It ASKS us to execute them
  by returning a special "tool_calls" response. We run the tool,
  send the result back, and let the LLM continue thinking.
"""

import json
from openai import OpenAI
from dotenv import load_dotenv

from tools import TOOL_SCHEMAS, TOOL_FUNCTIONS
from memory import ConversationMemory

# Load environment variables (.env file)
load_dotenv()

# Initialize the OpenAI client
# It automatically reads OPENAI_API_KEY from environment
client = OpenAI()

# ─────────────────────────────────────────────
# SYSTEM PROMPT — The Agent's Identity
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are a helpful Research Assistant agent. Your job is to help users
research topics, answer questions, and analyze information.

You have access to tools that let you:
- Calculate math expressions
- Read web pages to gather information
- Save and retrieve notes

INSTRUCTIONS:
1. Think step-by-step before acting.
2. When you need information, use your tools to get it.
3. Save important findings as notes so you can reference them later.
4. Provide clear, well-structured answers.
5. If you're unsure about something, say so honestly.
6. When doing research, read multiple sources when possible.

Always be helpful, accurate, and thorough."""

# Maximum number of tool-call loops to prevent infinite loops
MAX_ITERATIONS = 10


def run_agent(user_input: str, memory: ConversationMemory) -> str:
    """
    Run the agent loop for a single user request.

    This is THE core function — the agent loop:
    1. Send messages + tools to LLM
    2. Check if LLM wants to call tools
       - YES → Execute tools, add results, go to step 1
       - NO  → Return the LLM's text response

    Args:
        user_input: The user's message/question
        memory: The conversation memory manager

    Returns:
        The agent's final text response
    """

    # Add the user's message to memory
    memory.add_user_message(user_input)

    for iteration in range(MAX_ITERATIONS):
        print(f"\n🔄 Agent thinking... (iteration {iteration + 1})")

        # ── Step 1: Call the LLM ──────────────────────────
        response = client.chat.completions.create(
            model="gpt-4o-mini",       # Fast & cheap for development
            messages=memory.get_messages(),
            tools=TOOL_SCHEMAS,        # Tell the LLM what tools are available
            tool_choice="auto",        # Let the LLM decide when to use tools
        )

        # Get the assistant's message
        assistant_message = response.choices[0].message

        # Save assistant's response to memory
        # (We must convert to dict for storage)
        memory.add_assistant_message(assistant_message.to_dict())

        # ── Step 2: Check for tool calls ──────────────────
        if assistant_message.tool_calls:
            # The LLM wants to use tools! Let's execute them.
            print(f"🔧 Agent wants to use {len(assistant_message.tool_calls)} tool(s)")

            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"   → Calling: {tool_name}({tool_args})")

                # Execute the tool
                if tool_name in TOOL_FUNCTIONS:
                    result = TOOL_FUNCTIONS[tool_name](tool_args)
                else:
                    result = f"Error: Unknown tool '{tool_name}'"

                print(f"   ← Result: {result[:100]}...")  # Print first 100 chars

                # Feed the tool result back to the LLM
                memory.add_tool_result(tool_call.id, result)

            # Loop back to let the LLM think about the tool results
            continue

        # ── Step 3: No tool calls = Final answer ──────────
        final_response = assistant_message.content
        print(f"\n✅ Agent responded after {iteration + 1} iteration(s)")
        return final_response

    # Safety: If we hit max iterations, return what we have
    return "⚠️ I've reached my maximum thinking steps. Here's what I have so far: " + (
        assistant_message.content or "I wasn't able to reach a conclusion."
    )


def main():
    """
    Interactive chat loop — talk to your agent!

    Type your questions and the agent will:
    - Think about what it needs to do
    - Use tools if needed
    - Give you a researched answer
    """
    print("=" * 60)
    print("🤖 Research Assistant Agent")
    print("=" * 60)
    print("I can help you research topics, do calculations,")
    print("and read web pages. Type 'quit' to exit.\n")

    # Create memory with our system prompt
    memory = ConversationMemory(SYSTEM_PROMPT)

    while True:
        # Get user input
        user_input = input("\n👤 You: ").strip()

        # Check for exit commands
        if user_input.lower() in ("quit", "exit", "q"):
            print("\n👋 Goodbye! Happy researching!")
            break

        # Check for special commands
        if user_input.lower() == "clear":
            memory.clear()
            continue

        if not user_input:
            continue

        # Run the agent and print the response
        try:
            response = run_agent(user_input, memory)
            print(f"\n🤖 Agent: {response}")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Make sure your OPENAI_API_KEY is set correctly in .env")


if __name__ == "__main__":
    main()
