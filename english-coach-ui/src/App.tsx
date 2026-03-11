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
  full_corrected_text?: string
  full_corrected_text_tamil?: string
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
type AppTab = 'practice' | 'history' | 'test'

interface PracticeQuestion {
  id: number
  blank_sentence: string
  correct_answer: string
  wrong_word: string
  original_sentence: string
  corrected_sentence: string
  rule: string
  explanation: string
  tamil: string
}

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

// ─── Practice Test Component ─────────────────

function PracticeTest() {
  const [questions, setQuestions] = useState<PracticeQuestion[]>([])
  const [loading, setLoading] = useState(false)
  const [started, setStarted] = useState(false)
  const [current, setCurrent] = useState(0)
  const [userAnswer, setUserAnswer] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [results, setResults] = useState<{ correct: boolean; answer: string }[]>([])
  const [done, setDone] = useState(false)

  const loadQuestions = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/practice-test`)
      const data = await res.json()
      if (!data.questions || data.questions.length === 0) {
        setQuestions([])
        setStarted(true)
      } else {
        setQuestions(data.questions)
        setStarted(true)
        setCurrent(0)
        setResults([])
        setDone(false)
        setUserAnswer('')
        setSubmitted(false)
      }
    } catch {
      alert('Could not load questions. Make sure you have some practice history first!')
    }
    setLoading(false)
  }

  const checkAnswer = () => {
    const q = questions[current]
    const correct = userAnswer.trim().toLowerCase() === q.correct_answer.toLowerCase()
    setResults(r => [...r, { correct, answer: userAnswer.trim() }])
    setSubmitted(true)
  }

  const nextQuestion = () => {
    if (current + 1 >= questions.length) {
      setDone(true)
    } else {
      setCurrent(c => c + 1)
      setUserAnswer('')
      setSubmitted(false)
    }
  }

  const score = results.filter(r => r.correct).length

  // ── Not started yet ────────────────────────
  if (!started) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '40px 24px' }}>
        <div style={{ fontSize: '3.5rem', marginBottom: '12px' }}>🧪</div>
        <div className="card-title" style={{ marginBottom: '12px' }}>Practice Test</div>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '8px', lineHeight: 1.7 }}>
          This test is built from <strong style={{ color: 'var(--accent)' }}>your own mistakes</strong> across all practice sessions.
          Fill in the blank with the correct English word.
        </p>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '28px' }}>
          🏺 உங்கள் கடந்த கால தவறுகளில் இருந்து கேள்விகள் உருவாக்கப்படும்
        </p>
        <button className="analyze-btn" style={{ maxWidth: '220px', margin: '0 auto', display: 'block' }} onClick={loadQuestions} disabled={loading}>
          {loading ? '⏳ Loading questions...' : '▶ Start Test'}
        </button>
      </div>
    )
  }

  // ── No questions found ────────────────────
  if (started && questions.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '40px 24px' }}>
        <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>📭</div>
        <div className="card-title">No Mistakes Found!</div>
        <p style={{ color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          You haven't made any mistakes yet, or you have no practice history.
          Do a few practice sessions first, then come back here!
        </p>
        <button className="refresh-btn" style={{ marginTop: '20px' }} onClick={() => setStarted(false)}>← Back</button>
      </div>
    )
  }

  // ── Results screen ───────────────────────
  if (done) {
    const pct = Math.round((score / questions.length) * 100)
    return (
      <>
        <div className="card" style={{ textAlign: 'center', padding: '32px 24px' }}>
          <div style={{ fontSize: '3.5rem', marginBottom: '8px' }}>
            {pct >= 80 ? '🏆' : pct >= 50 ? '👍' : '💪'}
          </div>
          <div className="card-title" style={{ marginBottom: '8px' }}>Test Complete!</div>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: pct >= 80 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--error)', margin: '4px 0 8px' }}>
            {score} / {questions.length}
          </div>
          <div style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>{pct}% correct</div>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button className="analyze-btn" style={{ maxWidth: '160px' }} onClick={loadQuestions}>🔄 New Test</button>
            <button className="refresh-btn" onClick={() => setStarted(false)}>← Back</button>
          </div>
        </div>

        {/* Per-question review */}
        {questions.map((q, i) => {
          const r = results[i]
          return (
            <div key={i} className="card" style={{ borderLeft: `3px solid ${r?.correct ? 'var(--success)' : 'var(--error)'}` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                <span style={{ fontSize: '1.1rem' }}>{r?.correct ? '✅' : '❌'}</span>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Question {i + 1}</span>
              </div>
              <div style={{ color: 'var(--text-primary)', fontSize: '0.95rem', marginBottom: '6px', fontWeight: 500 }}>
                {q.blank_sentence.replace('_____', `[${q.correct_answer}]`)}
              </div>
              {!r?.correct && (
                <div style={{ fontSize: '0.85rem', color: 'var(--error)', marginBottom: '6px' }}>
                  You answered: <strong>"{r?.answer || '(empty)'}"</strong>
                </div>
              )}
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '3px' }}>📖 {q.rule}</div>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '3px' }}>{q.explanation}</div>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>🏺 {q.tamil}</div>
            </div>
          )
        })}
      </>
    )
  }

  // ── Active question ──────────────────────
  const q = questions[current]
  const currentResult = results[current]
  const parts = q.blank_sentence.split('_____')

  return (
    <div className="card">
      {/* Progress bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Question {current + 1} of {questions.length}</span>
        <span style={{ fontSize: '0.8rem', color: 'var(--success)' }}>✅ {results.filter(r => r.correct).length} correct</span>
      </div>
      <div className="score-bar" style={{ marginBottom: '24px' }}>
        <div className="score-bar-fill high" style={{ width: `${(current / questions.length) * 100}%`, transition: 'width 0.4s' }} />
      </div>

      {/* Sentence with blank rendered inline */}
      <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '10px' }}>
        Fill in the blank:
      </div>
      <div style={{ fontSize: '1.1rem', color: 'var(--text-primary)', lineHeight: 2, marginBottom: '8px' }}>
        {parts.map((part, i) => (
          <span key={i}>
            {part}
            {i < parts.length - 1 && (
              <span style={{
                display: 'inline-block',
                borderBottom: `2px solid ${submitted ? (currentResult?.correct ? 'var(--success)' : 'var(--error)') : 'var(--accent)'}`,
                minWidth: '90px',
                textAlign: 'center',
                color: submitted ? (currentResult?.correct ? 'var(--success)' : 'var(--error)') : 'var(--accent)',
                fontWeight: 700,
                padding: '0 6px',
                margin: '0 2px',
              }}>
                {submitted ? q.correct_answer : (userAnswer || '\u00a0\u00a0\u00a0\u00a0\u00a0')}
              </span>
            )}
          </span>
        ))}
      </div>

      <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '20px', fontStyle: 'italic' }}>
        You originally said: "{q.original_sentence}"
      </div>

      {/* Input or feedback */}
      {!submitted ? (
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <input
            style={{
              flex: 1, minWidth: '160px', padding: '10px 14px',
              background: 'var(--bg-secondary)', border: '1px solid var(--border)',
              borderRadius: '8px', color: 'var(--text-primary)', fontFamily: 'inherit',
              fontSize: '0.95rem', outline: 'none',
            }}
            placeholder="Type your answer..."
            value={userAnswer}
            onChange={e => setUserAnswer(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && userAnswer.trim() && checkAnswer()}
            autoFocus
          />
          <button className="analyze-btn" style={{ flex: 'none', padding: '10px 24px' }} disabled={!userAnswer.trim()} onClick={checkAnswer}>
            Submit
          </button>
        </div>
      ) : (
        <>
          <div style={{
            padding: '14px', borderRadius: '10px',
            background: currentResult?.correct ? 'var(--success-bg)' : 'var(--error-bg)',
            marginBottom: '14px',
          }}>
            <div style={{ fontWeight: 600, color: currentResult?.correct ? 'var(--success)' : 'var(--error)', marginBottom: '6px' }}>
              {currentResult?.correct ? '✅ Correct!' : `❌ Correct answer: "${q.correct_answer}"`}
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>📖 {q.rule}</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>{q.explanation}</div>
            <div style={{ fontSize: '0.83rem', color: 'var(--text-muted)' }}>🏺 {q.tamil}</div>
          </div>
          <button className="analyze-btn" onClick={nextQuestion}>
            {current + 1 >= questions.length ? '📊 See Results' : 'Next Question →'}
          </button>
        </>
      )}
    </div>
  )
}

// ─── Audio Upload Component ─────────────────


const ACCEPTED_AUDIO = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/wave', 'audio/x-wav',
  'audio/mp4', 'audio/m4a', 'audio/x-m4a', 'audio/ogg', 'audio/webm', 'audio/aac', 'audio/flac']

function AudioUpload({ onTranscript, onLoading }: {
  onTranscript: (text: string) => void
  onLoading: (v: boolean) => void
}) {
  const [isDragging, setIsDragging] = useState(false)
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    if (!ACCEPTED_AUDIO.includes(file.type) && !file.name.match(/\.(mp3|wav|m4a|ogg|webm|aac|flac)$/i)) {
      alert('Unsupported file format. Please upload MP3, WAV, M4A, OGG, WebM, AAC, or FLAC.')
      return
    }
    setUploadedFile(file)
    setUploadStatus('uploading')
    onLoading(true)
    try {
      const formData = new FormData()
      formData.append('audio', file, file.name)
      const res = await fetch(`${API}/api/transcribe`, { method: 'POST', body: formData })
      const data = await res.json()
      if (data.text) {
        onTranscript(data.text)
        setUploadStatus('done')
      } else {
        setUploadStatus('error')
      }
    } catch {
      setUploadStatus('error')
    }
    onLoading(false)
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const formatSize = (bytes: number) =>
    bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`

  return (
    <div className="upload-section">
      <div className="upload-divider"><span>or upload an audio file</span></div>
      <div
        className={`upload-zone ${isDragging ? 'dragging' : ''} ${uploadStatus === 'done' ? 'success' : ''} ${uploadStatus === 'error' ? 'error' : ''}`}
        onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*"
          style={{ display: 'none' }}
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
        />
        {uploadStatus === 'uploading' ? (
          <div className="upload-state">
            <div className="upload-spinner" />
            <span>Transcribing "{uploadedFile?.name}"...</span>
          </div>
        ) : uploadStatus === 'done' ? (
          <div className="upload-state">
            <span className="upload-icon">✅</span>
            <div>
              <div className="upload-filename">{uploadedFile?.name}</div>
              <div className="upload-meta">{formatSize(uploadedFile?.size || 0)} · Transcribed! Scroll down to edit &amp; analyze</div>
            </div>
            <button className="upload-retry" onClick={e => { e.stopPropagation(); setUploadStatus('idle'); setUploadedFile(null) }}>Upload another</button>
          </div>
        ) : uploadStatus === 'error' ? (
          <div className="upload-state">
            <span className="upload-icon">❌</span>
            <span>Transcription failed. Try again.</span>
          </div>
        ) : (
          <div className="upload-state">
            <span className="upload-icon">📂</span>
            <div>
              <div className="upload-hint-title">Drag &amp; drop an audio file</div>
              <div className="upload-hint-sub">MP3, WAV, M4A, OGG, WebM, AAC, FLAC · Click to browse</div>
            </div>
          </div>
        )}
      </div>
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
        <button className={`tab ${tab === 'test' ? 'active' : ''}`} onClick={() => { setTab('test'); setSelectedSession(null) }}>
          🧪 Test
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

            {/* Audio File Upload */}
            <AudioUpload
              onTranscript={text => { setTranscript(text); setAnalysis(null) }}
              onLoading={setLoading}
            />
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

      {tab === 'test' && <PracticeTest />}

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
  const [conversationView, setConversationView] = useState(false)

  return (
    <>
      {/* 🎧 Voice Coach */}
      <VoiceCoach analysis={analysis} />

      {/* View Mode Toggle */}
      <div className="view-toggle-bar">
        <span className="view-toggle-label">View Mode:</span>
        <div className="view-toggle-switch">
          <button
            className={`vtoggle-btn ${!conversationView ? 'active' : ''}`}
            onClick={() => setConversationView(false)}
          >
            📝 Detailed
          </button>
          <button
            className={`vtoggle-btn ${conversationView ? 'active' : ''}`}
            onClick={() => setConversationView(true)}
          >
            💬 Conversation
          </button>
        </div>
      </div>

      {/* Scores — always visible */}
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

      {conversationView ? (
        /* ─── CONVERSATION VIEW ─── */
        <div className="card">
          <div className="card-title">💬 Conversation View — Original vs Corrected</div>

          {/* Header row */}
          <div style={{ display: 'flex', gap: '0', borderBottom: '1px solid var(--border)', paddingBottom: '10px', marginBottom: '12px' }}>
            <div style={{ flex: 1, paddingRight: '12px', fontSize: '0.78rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--warning)' }}>
              💬 What You Said
            </div>
            <div style={{ width: '1px', background: 'var(--border)', flexShrink: 0, marginRight: '12px' }} />
            <div style={{ flex: 1, fontSize: '0.78rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--success)' }}>
              ✅ Corrected Version
            </div>
          </div>

          {/* If backend returned full corrected text, show side-by-side blocks */}
          {analysis.full_corrected_text ? (
            <div style={{ display: 'flex', gap: '0' }}>
              <div style={{ flex: 1, paddingRight: '12px', color: 'var(--text-secondary)', lineHeight: 1.7, fontSize: '0.95rem' }}>
                {analysis.sentences.map(s => s.original).join('\n\n')}
              </div>
              <div style={{ width: '1px', background: 'var(--border)', flexShrink: 0, marginRight: '12px' }} />
              <div style={{ flex: 1, color: 'var(--text-primary)', fontWeight: 500, lineHeight: 1.7, fontSize: '0.95rem' }}>
                {analysis.full_corrected_text}
              </div>
            </div>
          ) : (
            /* Sentence-by-sentence rows — always works */
            analysis.sentences.map((s, i) => (
              <div key={i} style={{
                display: 'flex',
                gap: '0',
                padding: '10px 0',
                borderBottom: i < analysis.sentences.length - 1 ? '1px solid var(--border)' : 'none',
              }}>
                <div style={{ flex: 1, paddingRight: '12px' }}>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.6 }}>
                    {s.original}
                  </div>
                  {!s.is_correct && s.errors.length > 0 && (
                    <div style={{ marginTop: '4px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {s.errors.map((err, j) => (
                        <span key={j} style={{ fontSize: '0.72rem', background: 'var(--error-bg)', color: 'var(--error)', padding: '2px 6px', borderRadius: '4px' }}>
                          {err.word} → {err.correction}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div style={{ width: '1px', background: s.is_correct ? 'rgba(0,200,83,0.2)' : 'var(--border)', flexShrink: 0, marginRight: '12px' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ color: s.is_correct ? 'var(--success)' : 'var(--text-primary)', fontWeight: s.is_correct ? 400 : 500, fontSize: '0.95rem', lineHeight: 1.6 }}>
                    {s.is_correct ? '✅ ' : ''}{s.corrected}
                  </div>
                </div>
              </div>
            ))
          )}

          {analysis.full_corrected_text_tamil && (
            <div className="conv-tamil" style={{ marginTop: '16px' }}>
              🏺 {analysis.full_corrected_text_tamil}
            </div>
          )}
        </div>
      ) : (
        /* ─── DETAILED VIEW ─── */
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
      )}

      {/* Summary — always visible */}
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
