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

import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

from tools import TOOL_SCHEMAS, TOOL_FUNCTIONS
from memory import ConversationMemory

# Load environment variables (.env file)
load_dotenv()

# ─────────────────────────────────────────────
# Initialize the client — Using Google Gemini!
# ─────────────────────────────────────────────
# Google provides an OpenAI-compatible endpoint so we can
# use the same `openai` SDK — just pointed at Google's servers.
client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

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

        # ── Step 1: Call the LLM (with retry for rate limits) ──
        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model="gemini-2.5-flash",       # Latest Gemini model, available for new users
                    messages=memory.get_messages(),
                    tools=TOOL_SCHEMAS,        # Tell the LLM what tools are available
                    tool_choice="auto",        # Let the LLM decide when to use tools
                )
                break  # Success! Exit retry loop
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    wait_time = 30 * (attempt + 1)  # 30s, 60s, 90s
                    print(f"⏳ Rate limited (free tier). Waiting {wait_time}s before retry...")
                    for remaining in range(wait_time, 0, -1):
                        print(f"   ⏱️  {remaining}s remaining...", end="\r")
                        time.sleep(1)
                    print("   ⏱️  Retrying now!          ")
                else:
                    raise  # Re-raise non-rate-limit errors

        # If all retries failed, bail out
        if response is None:
            return "⏳ Rate limit exceeded after all retries. Please wait a few minutes and try again."

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
            error_msg = str(e)
            print(f"\n❌ Error: {e}")
            if "401" in error_msg or "API key" in error_msg:
                print("🔑 Your API key seems invalid. Check your .env file.")
                print("   Get a free key at: https://aistudio.google.com/apikey")
            elif "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print("⏳ Rate limit hit. Wait a minute and try again.")
                print("   Free tier limits: https://ai.google.dev/gemini-api/docs/rate-limits")
            else:
                print("Make sure your GEMINI_API_KEY is set correctly in .env")


if __name__ == "__main__":
    main()
