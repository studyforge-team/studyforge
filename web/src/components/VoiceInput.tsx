import { useEffect, useRef, useState } from 'react'

// Web Speech is still prefixed in some browsers and absent from TypeScript's DOM types.
type Recognition = {
  lang: string
  continuous: boolean
  interimResults: boolean
  onstart: (() => void) | null
  onend: (() => void) | null
  onerror: ((event: { error: string }) => void) | null
  onresult: ((event: { results: ArrayLike<{ 0: { transcript: string }; isFinal: boolean }> }) => void) | null
  start(): void
  stop(): void
  abort(): void
}
type SpeechWindow = Window & {
  SpeechRecognition?: new () => Recognition
  webkitSpeechRecognition?: new () => Recognition
}

function release(recognition: Recognition) {
  recognition.onstart = recognition.onend = recognition.onerror = recognition.onresult = null
  recognition.abort()
}

export function VoiceInput({ disabled, onTranscript, onActiveChange }: {
  disabled: boolean
  onTranscript: (text: string) => void
  onActiveChange: (active: boolean) => void
}) {
  const recognitionRef = useRef<Recognition | null>(null)
  const [phase, setPhase] = useState<'idle' | 'starting' | 'listening' | 'stopping'>('idle')
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const speechWindow = window as SpeechWindow
  const Constructor = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition
  const supported = !!Constructor && window.isSecureContext
  const active = phase !== 'idle'

  useEffect(() => () => {
    if (recognitionRef.current) release(recognitionRef.current)
  }, [])

  function cancel() {
    if (recognitionRef.current) release(recognitionRef.current)
    recognitionRef.current = null
    setPhase('idle'); setTranscript(''); setMessage('Voice input cancelled.')
    onActiveChange(false)
  }

  function start() {
    if (!Constructor || !supported || disabled || recognitionRef.current) return
    setError(''); setMessage(''); setTranscript('')
    let finalText = ''
    let failed = false
    try {
      const recognition = new Constructor()
      recognitionRef.current = recognition
      recognition.lang = document.documentElement.lang || navigator.language || 'en-IN'
      // Android Chrome repeats final results in continuous mode (doubled words): one phrase per tap there
      recognition.continuous = !/Android/i.test(navigator.userAgent)
      recognition.interimResults = true
      recognition.onstart = () => setPhase('listening')
      recognition.onresult = ({ results }) => {
        const parts = Array.from(results)
        finalText = parts.filter((part) => part.isFinal).map((part) => part[0].transcript).join(' ').trim()
        setTranscript(parts.map((part) => part[0].transcript).join(' ').trim())
      }
      recognition.onerror = ({ error: code }) => {
        failed = true
        const errors: Record<string, string> = {
          'not-allowed': 'Microphone access was denied. Allow it in your browser settings, then try again.',
          'service-not-allowed': 'Your browser has disabled speech recognition. Try another browser or type your question.',
          'audio-capture': 'No microphone is available. Check your microphone connection and try again.',
          'no-speech': 'No speech was detected. Try again and speak clearly.',
          network: 'Speech recognition could not connect. Check your internet connection and try again.',
        }
        setError(errors[code] ?? 'Voice input stopped. Please try again or type your question.')
      }
      recognition.onend = () => {
        recognitionRef.current = null
        recognition.onstart = recognition.onend = recognition.onerror = recognition.onresult = null
        setPhase('idle'); setTranscript(''); onActiveChange(false)
        if (finalText) {
          onTranscript(finalText)
          setMessage('Voice input added. Review your question before solving.')
        } else if (!failed) setMessage('No speech was captured. Try again or type your question.')
      }
      setPhase('starting'); onActiveChange(true)
      recognition.start()
    } catch {
      if (recognitionRef.current) release(recognitionRef.current)
      recognitionRef.current = null
      setPhase('idle'); onActiveChange(false)
      setError('Voice input could not start. Check microphone permissions or type your question.')
    }
  }

  return (
    <div className="mt-2">
      <div className="flex items-center justify-end gap-2">
        {active && <button type="button" onClick={cancel} aria-label="Cancel voice input" className="min-h-11 rounded-full px-3 text-sm underline">Cancel</button>}
        <button type="button" aria-label={active ? 'Stop voice input' : 'Start voice input'} aria-pressed={active}
          aria-describedby="voice-help" disabled={!supported || disabled || phase === 'stopping'}
          onClick={() => {
            if (!active) { start(); return }
            setPhase('stopping')
            try { recognitionRef.current?.stop() } catch { cancel() }
          }}
          className={`flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:opacity-50 ${active ? 'bg-destructive text-white' : 'bg-primary text-primary-foreground'}`}>
          <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {active ? <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none" /> : <><rect x="9" y="2" width="6" height="13" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8" /></>}
          </svg>
        </button>
      </div>
      <p id="voice-help" className="mt-2 text-xs text-muted-foreground">{supported ? 'Tap the microphone to dictate. Your browser may send audio to its speech service. Review the text before solving.' : 'Voice input is not supported in this browser. You can still type your question.'}</p>
      <p role="status" className="mt-1 text-sm text-primary">{phase === 'starting' ? 'Starting microphone…' : phase === 'listening' ? 'Listening… Tap stop when finished.' : phase === 'stopping' ? 'Finishing voice input…' : message}</p>
      {active && transcript && <p className="mt-2 rounded-lg bg-muted p-3 text-sm" aria-label="Live transcript">{transcript}</p>}
      {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
    </div>
  )
}
