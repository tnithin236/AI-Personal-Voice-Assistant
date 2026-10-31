import { motion } from 'framer-motion'

const BARS = 32
const WEIGHTS = Array.from({ length: BARS }, (_, i) => 0.3 + 0.7 * Math.abs(Math.sin(i * 1.7 + 0.4)))

export const STAGE_LABEL = {
  idle: 'Hold the button, or hold Space, to talk',
  listening: 'Listening…',
  transcribing: 'Transcribing…',
  retrieving: 'Checking memory…',
  thinking: 'Thinking…',
  responding: 'Responding…',
  speaking: 'Speaking…',
}

/** Voice-activity animation: follows the real microphone level while listening. */
export default function VoiceStage({ stage, level, speaking, height = 64 }) {
  const mode = speaking ? 'speaking' : stage
  const live = mode === 'listening'
  const busy = mode !== 'idle' && !live
  return (
    <div className="flex items-center justify-center gap-[5px]" style={{ height }} aria-hidden="true">
      {WEIGHTS.map((w, i) =>
        busy ? (
          <span
            key={i}
            className="bar-wave w-[3px] rounded-full bg-stone-700"
            style={{ animationDelay: `${i * 45}ms` }}
          />
        ) : (
          <motion.span
            key={i}
            className={`w-[3px] rounded-full ${live ? 'bg-teal-700' : 'bg-stone-300'}`}
            animate={{ height: `${live ? 8 + Math.min(level, 1) * 92 * w : 8}%` }}
            transition={{ type: 'spring', stiffness: 380, damping: 24 }}
          />
        ),
      )}
    </div>
  )
}
