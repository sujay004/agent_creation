"""
🧠 LLM Module — Gemini Integration for English Analysis
=========================================================
Functions:
1. transcribe_audio() — Converts speech audio to text using Gemini
2. analyze_english() — Analyzes English text for grammar, fluency
3. generate_voice_script() — Creates conversational coaching text
4. generate_tts_audio() — Converts script to speech using Gemini TTS
"""

import os
import io
import json
import re
import wave
import random
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"
TTS_MODEL = "gemini-2.5-flash-preview-tts"


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


# ─────────────────────────────────────────────
# Voice Coach — Script Generation + TTS
# ─────────────────────────────────────────────

VOICE_SCRIPT_PROMPT = """You are a friendly English tutor coaching a Tamil-medium student.
Generate a SHORT spoken coaching script from this analysis. Keep it under 200 words.
Be conversational, warm, and encouraging — like a real tutor talking to the student.

Format: Plain text, no markdown, no JSON. Just what you would naturally say out loud.

Structure:
1. Start with a brief greeting and encouragement
2. For each sentence with errors: read the original, explain what's wrong, read the corrected version
3. For correct sentences: briefly praise them
4. End with 1-2 quick tips and encouragement

Example style:
"Great effort! Let me go through your sentences. You said 'I goed to school.' The word 'goed' should be 'went' — 'go' has an irregular past tense. So the correct sentence is: 'I went to school.' ... Keep practicing, you're doing really well!"

Analysis to convert:
{analysis_json}"""


def generate_voice_script(analysis: dict) -> str:
    """Generate a natural conversational coaching script from analysis results."""
    prompt = VOICE_SCRIPT_PROMPT.format(analysis_json=json.dumps(analysis, indent=2))
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text.strip()


def generate_tts_audio(script: str) -> bytes:
    """Convert a text script to WAV audio bytes using Gemini TTS."""
    response = client.models.generate_content(
        model=TTS_MODEL,
        contents=f"Say in a warm, encouraging, clear teacher voice: {script}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Kore",
                    )
                ),
            ),
        )
    )

    # Extract PCM audio data
    pcm_data = response.candidates[0].content.parts[0].inline_data.data

    # Convert PCM to WAV in memory
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm_data)

    return buf.getvalue()


def generate_tts_audio_from_analysis(analysis: dict) -> bytes:
    """One-step helper: analysis dict → coaching script → WAV audio bytes."""
    script = generate_voice_script(analysis)
    return generate_tts_audio(script)
