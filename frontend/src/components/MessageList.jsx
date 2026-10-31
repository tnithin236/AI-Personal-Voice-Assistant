import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Check, Copy, RefreshCw, Volume2, VolumeX, Wrench } from 'lucide-react'

function IconBtn({ onClick, title, children }) {
  return (
    <button onClick={onClick} title={title} className="rounded-md p-1.5 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700">
      {children}
    </button>
  )
}

function Message({ m, isLast, speaking, onSpeak, onStopSpeak, onRegenerate, busy }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try { await navigator.clipboard.writeText(m.content); setCopied(true); setTimeout(() => setCopied(false), 1200) } catch { /* ignore */ }
  }
  if (m.role === 'user') {
    return (
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-stone-200/70 px-4 py-2.5 text-[15px] leading-relaxed">
          {m.content}
          {m.voice && <span className="ml-2 align-middle text-[10px] uppercase tracking-wide text-stone-400">voice</span>}
        </div>
      </motion.div>
    )
  }
  const t = m.timings
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="group max-w-[88%]">
      {m.tool && (
        <div className="mb-1.5 inline-flex items-center gap-1.5 rounded-full border border-stone-200 px-2.5 py-0.5 text-xs text-stone-500">
          <Wrench size={11} /> {m.tool.replace('_', ' ')}
        </div>
      )}
      <div className="whitespace-pre-wrap text-[15px] leading-relaxed">
        {m.content}
        {m.streaming && <span className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 animate-pulse bg-stone-700" />}
      </div>
      {!m.streaming && (
        <div className="mt-1 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
          <IconBtn onClick={copy} title="Copy">{copied ? <Check size={15} /> : <Copy size={15} />}</IconBtn>
          <IconBtn onClick={speaking ? onStopSpeak : () => onSpeak(m.content)} title={speaking ? 'Stop speaking' : 'Speak'}>
            {speaking ? <VolumeX size={15} /> : <Volume2 size={15} />}
          </IconBtn>
          {isLast && !busy && <IconBtn onClick={onRegenerate} title="Regenerate"><RefreshCw size={15} /></IconBtn>}
          {t?.total_ms != null && (
            <span className="ml-2 text-[11px] text-stone-400"
              title={`retrieval ${t.retrieval_ms} ms · tool ${t.tool_ms} ms · first token ${t.first_token_ms ?? '–'} ms`}>
              {(t.total_ms / 1000).toFixed(1)}s{t.tokens_per_s ? ` · ${t.tokens_per_s} tok/s` : ''}
            </span>
          )}
        </div>
      )}
    </motion.div>
  )
}

export default function MessageList({ messages, speaking, busy, onSpeak, onStopSpeak, onRegenerate, thinking }) {
  const end = useRef(null)
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, thinking])
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')
  const streaming = messages[messages.length - 1]?.streaming
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-8">
        {messages.map((m) => (
          <Message key={m.key} m={m} isLast={m === lastAssistant} speaking={speaking}
            onSpeak={onSpeak} onStopSpeak={onStopSpeak} onRegenerate={onRegenerate} busy={busy} />
        ))}
        {thinking && !streaming && (
          <div className="flex gap-1.5 py-1">
            {[0, 1, 2].map((i) => (
              <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-stone-400" style={{ animationDelay: `${i * 120}ms` }} />
            ))}
          </div>
        )}
        <div ref={end} />
      </div>
    </div>
  )
}
