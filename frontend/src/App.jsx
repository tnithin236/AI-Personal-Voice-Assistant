import { useCallback, useRef, useState } from 'react'
import Sidebar from './components/Sidebar'
import { useAssistant } from './hooks/useAssistant'
import { useSettings } from './hooks/useSettings'
import { useSpeech } from './hooks/useSpeech'
import Assistant from './pages/Assistant'
import Documents from './pages/Documents'
import History from './pages/History'
import Memory from './pages/Memory'
import Settings from './pages/Settings'
import Tools from './pages/Tools'

export default function App() {
  const [page, setPage] = useState('assistant')
  const { settings, update, reset } = useSettings()
  const inputMode = useRef('text')
  const settingsRef = useRef(null)
  settingsRef.current = settings
  const streaming = useRef(false) // true while a reply is being spoken sentence-by-sentence

  const speechErr = useRef(null)
  const speech = useSpeech((m) => speechErr.current?.(m))
  const { startStream, feed, finish, speak, stop } = speech

  const shouldSpeak = useCallback(() => {
    const mode = settingsRef.current?.speak_replies ?? 'voice'
    return mode === 'always' || (mode === 'voice' && inputMode.current === 'voice')
  }, [])

  // Speak while the model is still writing: each finished sentence goes to the voice immediately.
  const onToken = useCallback((t) => {
    if (!shouldSpeak()) return
    if (!streaming.current) { streaming.current = true; startStream() }
    feed(t)
  }, [shouldSpeak, startStream, feed])

  const onReply = useCallback((ev) => {
    if (streaming.current) { streaming.current = false; finish() }
    else if (shouldSpeak() && ev.text) speak(ev.text) // e.g. tool confirmations that arrive without streaming
  }, [shouldSpeak, finish, speak])

  const onAbort = useCallback(() => { streaming.current = false; stop() }, [stop])

  const a = useAssistant({ onReply, onToken, onAbort })
  speechErr.current = a.setError

  const send = (text) => { inputMode.current = 'text'; stop(); a.sendText(text) }
  const talkStart = () => { inputMode.current = 'voice'; stop() }
  const updateSettings = (v) => update(v).catch((e) => a.setError(e.message))

  const open = async (id) => { await a.loadConversation(id); setPage('assistant') }
  const startNew = () => { a.newConversation(); setPage('assistant') }

  const pages = {
    assistant: <Assistant a={a} speech={speech} settings={settings} updateSettings={updateSettings} onTalkStart={talkStart} onSend={send} />,
    history: <History onOpen={open} onNew={startNew} activeId={a.conversationId} />,
    memory: <Memory settings={settings} updateSettings={updateSettings} />,
    documents: <Documents settings={settings} updateSettings={updateSettings} />,
    tools: <Tools settings={settings} updateSettings={updateSettings} />,
    settings: <Settings settings={settings} updateSettings={update} reset={reset} />,
  }

  return (
    <div className="flex h-full">
      <Sidebar page={page} onNavigate={setPage} connected={a.connected} />
      <main className="min-w-0 flex-1">{pages[page]}</main>
    </div>
  )
}
