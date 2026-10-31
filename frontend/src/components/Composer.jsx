import { useRef, useState } from 'react'
import { ArrowUp } from 'lucide-react'

export default function Composer({ onSend, disabled, leading }) {
  const [text, setText] = useState('')
  const ref = useRef(null)
  const submit = () => {
    if (!text.trim() || disabled) return
    onSend(text)
    setText('')
    if (ref.current) ref.current.style.height = 'auto'
  }
  return (
    <div className="flex items-end gap-3 rounded-2xl border border-stone-300 bg-white p-2 shadow-sm focus-within:border-stone-500">
      {leading}
      <textarea
        ref={ref}
        value={text}
        rows={1}
        placeholder="Type a message, or hold the mic to speak…"
        onChange={(e) => {
          setText(e.target.value)
          e.target.style.height = 'auto'
          e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px'
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
        }}
        className="max-h-40 flex-1 resize-none bg-transparent px-2 py-2.5 text-[15px] outline-none placeholder:text-stone-400"
      />
      <button
        onClick={submit}
        disabled={!text.trim() || disabled}
        title="Send"
        className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-stone-900 text-white transition-colors hover:bg-stone-700 disabled:bg-stone-200 disabled:text-stone-400"
      >
        <ArrowUp size={18} />
      </button>
    </div>
  )
}
