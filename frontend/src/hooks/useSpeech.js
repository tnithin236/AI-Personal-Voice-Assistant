import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../services/api'

function splitSentences(text) {
  const raw = text.replace(/\s+/g, ' ').trim().split(/(?<=[.!?\u0964])\s+/)
  const parts = []
  for (const s of raw) {
    if (parts.length && (parts[parts.length - 1].length < 40 || s.length < 12)) parts[parts.length - 1] += ' ' + s
    else parts.push(s)
  }
  return parts.flatMap((p) => (p.length > 300 ? p.match(/.{1,300}(\s|$)/g) : [p])).filter(Boolean)
}

/** Sentence-by-sentence playback: fetches the next sentence while the current one plays. */
export function useSpeech(onError) {
  const [speaking, setSpeaking] = useState(false)
  const audioRef = useRef(null)
  const runRef = useRef(0)
  const errRef = useRef(onError)
  errRef.current = onError

  const stop = useCallback(() => {
    runRef.current += 1
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null }
    setSpeaking(false)
  }, [])

  const speak = useCallback(async (text) => {
    stop()
    const id = runRef.current
    const parts = splitSentences(text)
    if (!parts.length) return
    const fetchPart = (p) => { const pr = api.tts(p); pr.catch(() => {}); return pr }
    setSpeaking(true)
    try {
      let next = fetchPart(parts[0])
      for (let i = 0; i < parts.length; i++) {
        const current = next
        if (i + 1 < parts.length) next = fetchPart(parts[i + 1])
        const blob = await current
        if (id !== runRef.current) return
        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audioRef.current = audio
        await new Promise((resolve) => {
          audio.onended = resolve
          audio.onerror = resolve
          audio.play().catch(resolve)
        })
        URL.revokeObjectURL(url)
        if (id !== runRef.current) return
      }
    } catch (e) {
      if (id === runRef.current) errRef.current?.(`Voice unavailable (showing text only): ${e.message}`)
    } finally {
      if (id === runRef.current) setSpeaking(false)
    }
  }, [stop])

  useEffect(() => stop, [stop])
  return { speaking, speak, stop }
}
