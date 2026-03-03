"""
🚀 English Coach API — FastAPI Backend
========================================
Endpoints:
  POST /api/transcribe  — Audio file → Gemini → transcribed text
  POST /api/analyze     — Text → Gemini → structured feedback JSON
  GET  /api/history     — Past sessions from SQLite
  GET  /api/topic       — Random practice topic
  GET  /api/sentence    — Random practice sentence
"""

import os
import json
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import llm
import database

app = FastAPI(title="English Coach API", version="1.0.0")

# Allow React frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RECORDINGS_DIR = Path(__file__).parent / "recordings"
RECORDINGS_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    text: str
    mode: str = "free_talk"  # free_talk, topic_based, sentence_reading


class AnalyzeResponse(BaseModel):
    overall_score: int
    grammar_score: int
    fluency_score: int
    sentences: list
    summary: str
    summary_tamil: str
    tips: list
    session_id: int


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "message": "English Coach API is running! 🎓"}


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """
    Receive audio file → send to Gemini → return transcribed text.
    Also saves the audio file for history.
    """
    try:
        audio_bytes = await audio.read()

        # Save recording
        filename = f"{uuid.uuid4().hex[:12]}.webm"
        filepath = RECORDINGS_DIR / filename
        with open(filepath, "wb") as f:
            f.write(audio_bytes)

        # Determine mime type
        mime_type = audio.content_type or "audio/webm"

        # Transcribe using Gemini
        text = llm.transcribe_audio(audio_bytes, mime_type)

        return {
            "text": text,
            "audio_filename": filename,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest):
    """
    Receive text → analyze with Gemini → return structured feedback.
    Saves the session to history.
    """
    try:
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        # Get analysis from Gemini
        analysis = llm.analyze_english(request.text, request.mode)

        # Save to history
        session_id = database.save_session(
            mode=request.mode,
            original_text=request.text,
            analysis=analysis,
        )

        return {**analysis, "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/api/transcribe-and-analyze")
async def transcribe_and_analyze(
    audio: UploadFile = File(...),
    mode: str = Form("free_talk"),
):
    """
    Combined endpoint: Audio → Transcribe → Analyze → Return feedback.
    One call does everything.
    """
    try:
        audio_bytes = await audio.read()

        # Save recording
        filename = f"{uuid.uuid4().hex[:12]}.webm"
        filepath = RECORDINGS_DIR / filename
        with open(filepath, "wb") as f:
            f.write(audio_bytes)

        mime_type = audio.content_type or "audio/webm"

        # Step 1: Transcribe
        text = llm.transcribe_audio(audio_bytes, mime_type)

        # Step 2: Analyze
        analysis = llm.analyze_english(text, mode)

        # Step 3: Save to history
        session_id = database.save_session(
            mode=mode,
            original_text=text,
            analysis=analysis,
            audio_filename=filename,
        )

        return {
            "transcribed_text": text,
            "audio_filename": filename,
            "session_id": session_id,
            **analysis,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.get("/api/history")
def get_history():
    """Return all past sessions."""
    sessions = database.get_sessions()
    # Parse the stored JSON string back to dict
    for s in sessions:
        if isinstance(s.get("analysis_json"), str):
            s["analysis"] = json.loads(s["analysis_json"])
            del s["analysis_json"]
    return {"sessions": sessions}


@app.get("/api/history/{session_id}")
def get_session(session_id: int):
    """Return a specific session."""
    session = database.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if isinstance(session.get("analysis_json"), str):
        session["analysis"] = json.loads(session["analysis_json"])
        del session["analysis_json"]
    return session


@app.get("/api/topic")
def get_topic():
    """Return a random practice topic."""
    return {"topic": llm.get_random_topic()}


@app.get("/api/sentence")
def get_sentence():
    """Return a random practice sentence."""
    return {"sentence": llm.get_random_sentence()}
