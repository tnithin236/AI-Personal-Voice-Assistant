import { Loader2, Mic, Square } from 'lucide-react'
import { motion } from 'framer-motion'
import { BUSY_STAGES } from '../hooks/useAssistant'

/** Push-to-talk: press and hold. While the assistant is working, the button becomes "stop". */
export default function MicButton({ stage, onDown, onUp, onCancel, disabled, size = 'lg' }) {
  const busy = BUSY_STAGES.includes(stage)
  const listening = stage === 'listening'
  const dim = size === 'lg' ? 'h-16 w-16' : 'h-11 w-11'
  const Icon = busy ? (size === 'lg' ? Loader2 : Square) : listening ? Square : Mic

  return (
    <motion.button
      type="button"
      disabled={disabled}
      whileTap={{ scale: 0.94 }}
      onPointerDown={(e) => {
        if (busy) { onCancel(); return }
        e.currentTarget.setPointerCapture(e.pointerId)
        onDown()
      }}
      onPointerUp={onUp}
      onPointerCancel={onUp}
      onContextMenu={(e) => e.preventDefault()}
      title={busy ? 'Stop' : 'Hold to talk'}
      className={`relative grid shrink-0 select-none place-items-center rounded-full text-white shadow-sm transition-colors disabled:opacity-40 ${dim} ${
        listening ? 'bg-teal-700' : 'bg-stone-900 hover:bg-stone-700'
      }`}
    >
      {listening && <span className="absolute inset-0 animate-ping rounded-full bg-teal-700/30" />}
      <Icon size={size === 'lg' ? 24 : 18} strokeWidth={1.75} className={busy && size === 'lg' ? 'animate-spin' : ''} />
    </motion.button>
  )
}
