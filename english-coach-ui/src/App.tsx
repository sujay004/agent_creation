import { useState, useEffect, useRef } from 'react'
import './index.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ─── Types ──────────────────────────────────

interface ErrorDetail {
  word: string
  correction: string
  rule: string
  explanation: string
  tamil: string
}

interface SentenceFeedback {
  original: string
  corrected: string
  is_correct: boolean
  errors: ErrorDetail[]
}

interface Analysis {
  overall_score: number
  grammar_score: number
  fluency_score: number
  sentences: SentenceFeedback[]
  summary: string
  summary_tamil: string
  tips: string[]
  session_id?: number
  voice_script?: string
}

interface HistorySession {
  id: number
  timestamp: string
  mode: string
  original_text: string
  overall_score: number
  grammar_score: number
  fluency_score: number
  analysis?: Analysis
}

type PracticeMode = 'free_talk' | 'topic_based' | 'sentence_reading'
type SttMode = 'browser' | 'gemini'
type AppTab = 'practice' | 'history'

// ─── Score helpers ──────────────────────────

function scoreClass(score: number) {
  if (score >= 7) return 'high'
  if (score >= 4) return 'mid'
  return 'low'
}

// ─── Voice Coach Component ──────────────────

function VoiceCoach({ analysis }: { analysis: Analysis }) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [usedGemini, setUsedGemini] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)

  const stopAll = () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.src = ''
    }
    window.speechSynthesis?.cancel()
    setIsPlaying(false)
  }

  // ── Try Gemini TTS first, fallback to browser ──
  const playVoiceFeedback = async () => {
    stopAll()
    setIsLoading(true)

    try {
      // Try Gemini TTS endpoint
      const res = await fetch(`${API}/api/voice-feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis }),
      })

      if (res.ok) {
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audioRef.current = audio
        audio.onended = () => {
          setIsPlaying(false)
          URL.revokeObjectURL(url)
        }
        audio.onerror = () => {
          setIsPlaying(false)
          URL.revokeObjectURL(url)
        }
        setIsLoading(false)
        setIsPlaying(true)
        setUsedGemini(true)
        audio.play()
        return
      }
    } catch (_) {
      // Fall through to browser TTS
    }

    // ── Browser SpeechSynthesis fallback ──
    setUsedGemini(false)
    const script = analysis.voice_script || buildBrowserScript(analysis)

    if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(script)
      utterance.lang = 'en-IN'
      utterance.rate = 0.9
      utterance.pitch = 1.0

      // Prefer a female voice for the "tutor" feel
      const voices = window.speechSynthesis.getVoices()
      const preferred = voices.find(v => v.lang.startsWith('en') && v.name.includes('Female'))
        || voices.find(v => v.lang.startsWith('en'))
      if (preferred) utterance.voice = preferred

      utterance.onend = () => setIsPlaying(false)
      utterance.onerror = () => setIsPlaying(false)

      utteranceRef.current = utterance
      setIsLoading(false)
      setIsPlaying(true)
      window.speechSynthesis.speak(utterance)
    } else {
      setIsLoading(false)
      alert('Audio playback is not supported in this browser. Please use Chrome.')
    }
  }

  const handleStop = () => {
    stopAll()
  }

  // Build a script from analysis for browser TTS (when voice_script not available)
  const buildBrowserScript = (a: Analysis): string => {
    let script = 'Great effort on your English practice! Let me go through your sentences. '
    a.sentences.forEach((s, i) => {
      if (s.is_correct) {
        script += `Sentence ${i + 1}: "${s.original}" — This is perfect! Well done. `
      } else {
        script += `Sentence ${i + 1}: You said — "${s.original}". `
        if (s.errors.length > 0) {
          s.errors.forEach(e => {
            script += `The word "${e.word}" should be "${e.correction}". ${e.explanation}. `
          })
        }
        script += `The correct sentence is: "${s.corrected}". `
      }
    })
    script += `Overall you scored ${a.overall_score} out of 10. Keep practicing and you will improve!`
    return script
  }

  return (
    <div className="voice-coach-bar">
      <div className="voice-coach-info">
        <span className="voice-coach-icon">🎧</span>
        <div>
          <div className="voice-coach-title">Live Voice Coach</div>
          <div className="voice-coach-sub">
            {isLoading ? 'Generating audio...'
              : isPlaying ? (usedGemini ? '🤖 Gemini AI speaking...' : '🔊 Coach speaking...')
              : 'Hear your corrections spoken aloud'}
          </div>
        </div>
      </div>
      <div className="voice-coach-controls">
        {isPlaying ? (
          <button className="vc-btn vc-stop" onClick={handleStop}>⏹ Stop</button>
        ) : (
          <button className="vc-btn vc-play" disabled={isLoading} onClick={playVoiceFeedback}>
            {isLoading ? (
              <span className="vc-loading">⏳ Generating...</span>
            ) : (
              <>▶ Listen to Coach</>
            )}
          </button>
        )}
      </div>
      {isPlaying && (
        <div className="voice-waveform">
          {[...Array(12)].map((_, i) => (
            <div key={i} className="wave-bar" style={{ animationDelay: `${i * 0.08}s` }} />
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Main App ───────────────────────────────

function App() {
  const [tab, setTab] = useState<AppTab>('practice')
  const [mode, setMode] = useState<PracticeMode>('free_talk')
  const [sttMode, setSttMode] = useState<SttMode>('browser')
  const [isRecording, setIsRecording] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [prompt, setPrompt] = useState('')
  const [history, setHistory] = useState<HistorySession[]>([])
  const [selectedSession, setSelectedSession] = useState<Analysis | null>(null)
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null)
  const [recognition, setRecognition] = useState<any>(null)

  // Fetch prompt when mode changes
  useEffect(() => {
    if (mode === 'topic_based') {
      fetch(`${API}/api/topic`).then(r => r.json()).then(d => setPrompt(d.topic)).catch(() => {})
    } else if (mode === 'sentence_reading') {
      fetch(`${API}/api/sentence`).then(r => r.json()).then(d => setPrompt(d.sentence)).catch(() => {})
    }
  }, [mode])

  // Fetch history when tab switches
  useEffect(() => {
    if (tab === 'history') {
      fetch(`${API}/api/history`).then(r => r.json()).then(d => setHistory(d.sessions || [])).catch(() => {})
    }
  }, [tab])

  const refreshPrompt = () => {
    if (mode === 'topic_based') {
      fetch(`${API}/api/topic`).then(r => r.json()).then(d => setPrompt(d.topic))
    } else if (mode === 'sentence_reading') {
      fetch(`${API}/api/sentence`).then(r => r.json()).then(d => setPrompt(d.sentence))
    }
  }

  // ── Recording with Browser STT ────────────
  const startBrowserRecording = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRecognition) {
      alert('Browser speech recognition not supported. Please use Gemini mode or try Chrome.')
      return
    }
    const recog = new SpeechRecognition()
    recog.continuous = true
    recog.interimResults = false
    recog.lang = 'en-IN'

    let fullText = ''
    recog.onresult = (e: any) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          fullText += e.results[i][0].transcript + ' '
          setTranscript(fullText.trim())
        }
      }
    }
    recog.onerror = (e: any) => console.error('Speech error:', e.error)
    recog.start()
    setRecognition(recog)
    setIsRecording(true)
  }

  const stopBrowserRecording = () => {
    recognition?.stop()
    setRecognition(null)
    setIsRecording(false)
  }

  // ── Recording with Gemini STT ─────────────
  const startGeminiRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      const chunks: BlobPart[] = []

      recorder.ondataavailable = (e) => chunks.push(e.data)
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunks, { type: 'audio/webm' })
        const formData = new FormData()
        formData.append('audio', blob, 'recording.webm')

        setLoading(true)
        try {
          const res = await fetch(`${API}/api/transcribe`, { method: 'POST', body: formData })
          const data = await res.json()
          if (data.text) setTranscript(data.text)
        } catch (err) {
          console.error('Transcription error:', err)
        }
        setLoading(false)
      }

      recorder.start()
      setMediaRecorder(recorder)
      setIsRecording(true)
    } catch (err) {
      alert('Microphone access denied. Please allow microphone access.')
    }
  }

  const stopGeminiRecording = () => {
    mediaRecorder?.stop()
    setMediaRecorder(null)
    setIsRecording(false)
  }

  const toggleRecording = () => {
    if (isRecording) {
      sttMode === 'browser' ? stopBrowserRecording() : stopGeminiRecording()
    } else {
      setTranscript('')
      setAnalysis(null)
      sttMode === 'browser' ? startBrowserRecording() : startGeminiRecording()
    }
  }

  // ── Analyze transcript ────────────────────
  const analyzeText = async () => {
    if (!transcript.trim()) return
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: transcript, mode }),
      })
      const data = await res.json()
      setAnalysis(data)
    } catch (err) {
      console.error('Analysis error:', err)
    }
    setLoading(false)
  }

  const viewSession = (session: HistorySession) => {
    if (session.analysis) {
      setSelectedSession(session.analysis)
    }
  }

  // ─── Render ───────────────────────────────

  return (
    <div className="app">
      <header className="header">
        <h1>🎓 English Coach</h1>
        <p>Speak. Learn. Improve. — உங்கள் ஆங்கிலத்தை மேம்படுத்துங்கள்</p>
      </header>

      <div className="tabs">
        <button className={`tab ${tab === 'practice' ? 'active' : ''}`} onClick={() => { setTab('practice'); setSelectedSession(null) }}>
          🎤 Practice
        </button>
        <button className={`tab ${tab === 'history' ? 'active' : ''}`} onClick={() => { setTab('history'); setSelectedSession(null) }}>
          📜 History
        </button>
      </div>

      {tab === 'practice' && (
        <>
          {/* Mode Selector */}
          <div className="card">
            <div className="card-title">Practice Mode</div>
            <div className="mode-selector">
              <button className={`mode-btn ${mode === 'free_talk' ? 'active' : ''}`} onClick={() => setMode('free_talk')}>
                <span className="mode-emoji">💬</span>Free Talk
              </button>
              <button className={`mode-btn ${mode === 'topic_based' ? 'active' : ''}`} onClick={() => setMode('topic_based')}>
                <span className="mode-emoji">📝</span>Topic Based
              </button>
              <button className={`mode-btn ${mode === 'sentence_reading' ? 'active' : ''}`} onClick={() => setMode('sentence_reading')}>
                <span className="mode-emoji">📖</span>Read Aloud
              </button>
            </div>
          </div>

          {/* Topic / Sentence Prompt */}
          {mode !== 'free_talk' && prompt && (
            <div className="prompt-card">
              <div className="prompt-label">{mode === 'topic_based' ? '🎯 Your Topic' : '📖 Read This Sentence'}</div>
              <div className="prompt-text">{prompt}</div>
              <button className="refresh-btn" onClick={refreshPrompt}>🔄 New {mode === 'topic_based' ? 'Topic' : 'Sentence'}</button>
            </div>
          )}

          {/* Recorder */}
          <div className="card">
            <div className="stt-selector">
              <label>🎙️ Speech Recognition:</label>
              <select value={sttMode} onChange={e => setSttMode(e.target.value as SttMode)}>
                <option value="browser">Browser (Free, Instant)</option>
                <option value="gemini">Gemini AI (More Accurate)</option>
              </select>
            </div>

            <div className="recorder">
              <button className={`mic-btn ${isRecording ? 'recording' : ''}`} onClick={toggleRecording}>
                {isRecording ? '⏹️' : '🎤'}
              </button>
              <span className={`recorder-status ${isRecording ? 'recording' : ''}`}>
                {isRecording ? '🔴 Recording... Click to stop' : 'Click microphone to start'}
              </span>
            </div>
          </div>

          {/* Transcript */}
          <div className="card">
            <div className="card-title">Your Speech</div>
            <textarea
              className="transcript-area"
              placeholder="Your speech will appear here... You can also type or edit the text."
              value={transcript}
              onChange={e => setTranscript(e.target.value)}
            />
            <button className="analyze-btn" disabled={!transcript.trim() || loading} onClick={analyzeText}>
              {loading ? '⏳ Analyzing...' : '🔍 Analyze My English'}
            </button>
          </div>

          {/* Loading */}
          {loading && (
            <div className="loading">
              <div className="spinner" />
              <span>Analyzing your English with AI...</span>
            </div>
          )}

          {/* Results */}
          {analysis && <FeedbackDisplay analysis={analysis} />}
        </>
      )}

      {tab === 'history' && !selectedSession && (
        <HistoryList history={history} onSelect={viewSession} />
      )}

      {selectedSession && (
        <>
          <button className="refresh-btn" style={{ marginBottom: 16 }} onClick={() => setSelectedSession(null)}>
            ← Back to History
          </button>
          <FeedbackDisplay analysis={selectedSession} />
        </>
      )}
    </div>
  )
}

// ─── Feedback Component ───────────────────────

function FeedbackDisplay({ analysis }: { analysis: Analysis }) {
  return (
    <>
      {/* 🎧 Voice Coach — appears at the top of results, prominent */}
      <VoiceCoach analysis={analysis} />

      {/* Scores */}
      <div className="card">
        <div className="card-title">Your Scores</div>
        <div className="scores">
          {[
            { label: 'Overall', score: analysis.overall_score },
            { label: 'Grammar', score: analysis.grammar_score },
            { label: 'Fluency', score: analysis.fluency_score },
          ].map(s => (
            <div className="score-card" key={s.label}>
              <div className={`score-value ${scoreClass(s.score)}`}>{s.score}/10</div>
              <div className="score-label">{s.label}</div>
              <div className="score-bar">
                <div className={`score-bar-fill ${scoreClass(s.score)}`} style={{ width: `${s.score * 10}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Sentence-by-Sentence */}
      <div className="card">
        <div className="card-title">Sentence-by-Sentence Feedback</div>
        {analysis.sentences.map((s, i) => (
          <div className={`sentence-item ${s.is_correct ? 'correct' : 'has-errors'}`} key={i}>
            <div className="sentence-label" style={{ color: 'var(--text-muted)' }}>You said:</div>
            <div className="sentence-original">"{s.original}"</div>
            {!s.is_correct && (
              <>
                <div className="sentence-label" style={{ color: 'var(--success)' }}>Corrected:</div>
                <div className="sentence-corrected">✅ "{s.corrected}"</div>
              </>
            )}
            {s.is_correct && <span className="correct-badge">✅ Perfect!</span>}
            {s.errors.map((err, j) => (
              <div className="error-item" key={j}>
                <div className="error-word">
                  <span className="error-wrong">{err.word}</span>
                  <span className="error-arrow">→</span>
                  <span className="error-correct">{err.correction}</span>
                </div>
                <div className="error-rule">{err.rule}</div>
                <div className="error-explanation">{err.explanation}</div>
                <div className="error-tamil">{err.tamil}</div>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="card">
        <div className="card-title">Summary & Tips</div>
        <div className="summary-text">{analysis.summary}</div>
        <div className="summary-tamil">{analysis.summary_tamil}</div>
        {analysis.tips && analysis.tips.length > 0 && (
          <ul className="tips-list">
            {analysis.tips.map((tip, i) => <li key={i}>{tip}</li>)}
          </ul>
        )}
      </div>
    </>
  )
}

// ─── History Component ────────────────────────

function HistoryList({ history, onSelect }: { history: HistorySession[]; onSelect: (s: HistorySession) => void }) {
  if (history.length === 0) {
    return (
      <div className="card">
        <div className="empty-state">
          <div className="empty-state-emoji">📭</div>
          <div className="empty-state-text">No practice sessions yet. Start speaking to build your history!</div>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-title">Past Sessions</div>
      {history.map(s => (
        <div className="history-item" key={s.id} onClick={() => onSelect(s)}>
          <div className="history-meta">
            <span className="history-date">{new Date(s.timestamp).toLocaleString()}</span>
            <span className="history-mode">{s.mode.replace('_', ' ')}</span>
            <span className="history-text-preview">{s.original_text}</span>
          </div>
          <div className={`history-score ${scoreClass(s.overall_score)}`}>{s.overall_score}/10</div>
        </div>
      ))}
    </div>
  )
}

export default App
