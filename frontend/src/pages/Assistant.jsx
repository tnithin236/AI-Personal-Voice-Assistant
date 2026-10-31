import { useEffect, useRef } from 'react'
import { Eraser, Plus, X } from 'lucide-react'
import { BUSY_STAGES } from '../hooks/useAssistant'
import Composer from '../components/Composer'
import ConfirmCard from '../components/ConfirmCard'
import LanguageSelect from '../components/LanguageSelect'
import MessageList from '../components/MessageList'
import MicButton from '../components/MicButton'
import { Button } from '../components/PageHeader'
import VoiceStage, { STAGE_LABEL } from '../components/VoiceStage'

const SUGGESTIONS = [
  "What's the time?", 'Calculate 15% of 2,480', 'Search the web for today’s top tech news',
  'Remember that my favourite colour is green', 'தமிழில் ஒரு சிறிய கதை சொல்லு',
]

export default function Assistant({ a, speech, settings, updateSettings, onTalkStart, onSend }) {
  const holding = useRef(false)
  const busy = BUSY_STAGES.includes(a.stage)
  const stageNow = speech.speaking && a.stage === 'idle' ? 'speaking' : a.stage

  const down = () => {
    if (holding.current || !a.connected) return
    holding.current = true
    onTalkStart()
    a.startVoice()
  }
  const up = () => {
    if (!holding.current) return
    holding.current = false
    a.stopVoice()
  }

  // Space = push-to-talk (ignored while typing in a field)
  const downRef = useRef(down); downRef.current = down
  const upRef = useRef(up); upRef.current = up
  const busyRef = useRef(busy); busyRef.current = busy
  useEffect(() => {
    const typing = (t) => ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(t?.tagName)
    const kd = (e) => { if (e.code === 'Space' && !e.repeat && !typing(e.target) && !busyRef.current) { e.preventDefault(); downRef.current() } }
    const ku = (e) => { if (e.code === 'Space') upRef.current() }
    window.addEventListener('keydown', kd)
    window.addEventListener('keyup', ku)
    return () => { window.removeEventListener('keydown', kd); window.removeEventListener('keyup', ku) }
  }, [])

  const empty = a.messages.length === 0
  const mic = (size) => (
    <MicButton stage={a.stage} size={size} disabled={!a.connected} onDown={down} onUp={up} onCancel={a.cancel} />
  )

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-stone-200 px-8 py-4">
        <h1 className="text-lg font-semibold tracking-tight">Assistant</h1>
        <div className="flex items-center gap-2">
          {settings && <LanguageSelect value={settings.language} onChange={(language) => updateSettings({ language })} />}
          <Button variant="ghost" onClick={a.newConversation} title="New conversation"><Plus size={16} /> New</Button>
          <Button variant="ghost" onClick={a.clearConversation} disabled={empty} title="Clear conversation"><Eraser size={16} /> Clear</Button>
        </div>
      </header>

      {a.error && (
        <div className="mx-auto mt-4 flex w-full max-w-3xl items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm text-rose-800">
          <span className="flex-1">{a.error}</span>
          <button onClick={() => a.setError(null)}><X size={16} /></button>
        </div>
      )}

      {empty ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6">
          <div className="text-center">
            <h2 className="text-2xl font-semibold tracking-tight">How can I help?</h2>
            <p className="mt-1 text-sm text-stone-500">Runs locally on your computer · English and தமிழ்</p>
          </div>
          <VoiceStage stage={stageNow} level={a.level} speaking={speech.speaking} height={88} />
          {mic('lg')}
          <p className="text-sm text-stone-500">{STAGE_LABEL[stageNow] || ''}</p>
          <div className="flex max-w-2xl flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => onSend(s)} className="rounded-full border border-stone-300 bg-white px-3.5 py-1.5 text-sm text-stone-600 transition-colors hover:bg-stone-100">
                {s}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <MessageList
          messages={a.messages} speaking={speech.speaking} busy={busy} thinking={busy && a.stage !== 'responding'}
          onSpeak={(t) => speech.speak(t)} onStopSpeak={speech.stop} onRegenerate={a.regenerate}
        />
      )}

      <div className="px-6 pb-6 pt-2">
        <div className="mx-auto flex max-w-3xl flex-col gap-3">
          {a.pending && <ConfirmCard pending={a.pending} onApprove={() => a.confirmAction(true)} onDeny={() => a.confirmAction(false)} />}
          {!empty && (a.stage !== 'idle' || speech.speaking) && (
            <div className="flex items-center justify-center gap-4">
              <VoiceStage stage={stageNow} level={a.level} speaking={speech.speaking} height={28} />
              <span className="text-xs text-stone-500">{STAGE_LABEL[stageNow]}</span>
              {speech.speaking && <Button variant="ghost" className="px-2.5! py-1! text-xs" onClick={speech.stop}>Stop speaking</Button>}
            </div>
          )}
          <Composer onSend={onSend} disabled={busy || !a.connected} leading={empty ? null : mic('sm')} />
        </div>
      </div>
    </div>
  )
}
