"""
🧠 LLM Module — Gemini Integration for English Analysis
=========================================================
Two main functions:
1. transcribe_audio() — Converts speech audio to text using Gemini
2. analyze_english() — Analyzes English text for grammar, fluency,
   provides corrections with Tamil translations
"""

import os
import json
import re
import random
from google import genai
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"


# ─────────────────────────────────────────────
# Speech-to-Text using Gemini
# ─────────────────────────────────────────────

def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """
    Send audio to Gemini and get transcription.
    Gemini can directly process audio input.
    """
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            "Transcribe the following audio accurately. "
            "The speaker is a Tamil-medium student practicing English. "
            "Transcribe exactly what they say, including any grammatical errors or mispronunciations. "
            "Do NOT correct anything. Just transcribe word-for-word. "
            "Return ONLY the transcribed text, nothing else.",
            genai.types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
        ]
    )
    return response.text.strip()


# ─────────────────────────────────────────────
# English Analysis using Gemini
# ─────────────────────────────────────────────

ANALYSIS_PROMPT = """You are an expert English language tutor helping a Tamil-medium student improve their English.

Analyze the following English text spoken by the student. Provide detailed, encouraging feedback.

IMPORTANT: Respond ONLY with valid JSON in this exact format (no markdown, no code blocks):
{{
  "overall_score": <1-10>,
  "grammar_score": <1-10>,
  "fluency_score": <1-10>,
  "sentences": [
    {{
      "original": "<exact sentence the student said>",
      "corrected": "<the grammatically correct version>",
      "is_correct": <true/false>,
      "errors": [
        {{
          "word": "<the incorrect word or phrase>",
          "correction": "<the correct word or phrase>",
          "rule": "<grammar rule name, e.g. 'Subject-Verb Agreement'>",
          "explanation": "<brief English explanation of why it's wrong and how to fix it>",
          "tamil": "<the same explanation translated to Tamil>"
        }}
      ]
    }}
  ],
  "summary": "<2-3 sentence overall feedback in English. Be encouraging but specific.>",
  "summary_tamil": "<same feedback translated to Tamil>",
  "tips": ["<tip 1>", "<tip 2>", "<tip 3>"]
}}

RULES:
- If a sentence is correct, set is_correct to true and errors to []
- Still include correct sentences in the output with corrected = original
- Score 1-10 where 10 is perfect
- Be encouraging — this student is learning!
- Tamil translations should be natural, not literal
- Focus on the most impactful errors first
- If the text mentions the practice mode, ignore it and analyze only the English content

PRACTICE MODE: {mode}

STUDENT'S TEXT:
{text}"""


def analyze_english(text: str, mode: str = "free_talk") -> dict:
    """
    Analyze English text and return structured feedback
    with grammar corrections, explanations, and Tamil translations.
    """
    prompt = ANALYSIS_PROMPT.format(text=text, mode=mode)

    response = client.models.generate_content(model=MODEL, contents=prompt)

    # Parse the JSON response — handle various formats Gemini may return
    raw = response.text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                result = _fallback_result(raw)
        else:
            result = _fallback_result(raw)

    return result


def _fallback_result(raw_text: str) -> dict:
    return {
        "overall_score": 5,
        "grammar_score": 5,
        "fluency_score": 5,
        "sentences": [],
        "summary": raw_text[:500],
        "summary_tamil": "",
        "tips": []
    }


# ─────────────────────────────────────────────
# Topic Suggestions
# ─────────────────────────────────────────────

TOPICS = [
    "Describe your favorite food and how it is made",
    "Tell me about your family members",
    "What did you do last weekend?",
    "Describe your school or college",
    "What do you want to become in the future and why?",
    "Talk about your favorite festival",
    "Describe the weather today",
    "Tell me about your best friend",
    "What is your favorite movie and why?",
    "Describe your hometown or village",
    "What do you usually do in the morning?",
    "Talk about a place you want to visit",
]

PRACTICE_SENTENCES = [
    "The quick brown fox jumps over the lazy dog.",
    "I went to the market yesterday and bought some vegetables.",
    "She has been studying English for three years.",
    "If I had more time, I would learn to play the guitar.",
    "The children were playing in the park when it started raining.",
    "My mother cooks delicious food every Sunday.",
    "He asked me whether I could help him with his homework.",
    "The train arrives at the station at half past nine.",
    "We are planning to visit our grandparents next month.",
    "She told me that she had already finished her work.",
]

def get_random_topic() -> str:
    return random.choice(TOPICS)

def get_random_sentence() -> str:
    return random.choice(PRACTICE_SENTENCES)
