import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../services/api'

const MIN_CHARS = 15   // very short sentences are merged with the next one
const MAX_CHARS = 300  // long sentences are split so each TTS request stays quick
const SENTENCE = /^([\s\S]*?[.!?\u0964]+["')\]]*)\s+/

export function takeSentences(buffer, final) {
  const out = []
  let rest = buffer
  for (;;) {
    const m = rest.match(SENTENCE)
    if (!m) break
    out.push(m[1].trim())
    rest = rest.slice(m[0].length)
  }
  if (final && rest.trim()) { out.push(rest.trim()); rest = '' }
  return [out, rest]
}

export function splitLong(text) {
  const parts = []
  let rest = text
  while (rest.length > MAX_CHARS) {
    let cut = rest.lastIndexOf(' ', MAX_CHARS)
    if (cut < MAX_CHARS / 2) cut = MAX_CHARS
    parts.push(rest.slice(0, cut).trim())
    rest = rest.slice(cut).trim()
  }
  if (rest) parts.push(rest)
  return parts
}

const ensure = (item) => {
  if (item && !item.promise) {
    item.promise = api.tts(item.text)
    item.promise.catch(() => {}) // errors are handled where the promise is awaited
  }
}
const poke = (st) => { const w = st.wake; st.wake = null; if (w) w() }

/**
 * Streaming speech. State is one of:
 *   idle       nothing queued
 *   preparing  text is being turned into audio (or waiting for the next sentence)
 *   speaking   audio is ACTUALLY playing (set from the <audio> "playing" event)
 * Usage: startStream() -> feed(textChunk)... -> finish()   or   speak(fullText)
 */
export function useSpeech(onError) {
  const [state, setState] = useState('idle')
  const errRef = useRef(onError)
  errRef.current = onError
  const S = useRef({
    id: 0, runId: -1, queue: [], buffer: '', carry: '', closed: true, failed: false,
    audio: null, wake: null, endPlay: null,
  })

  const run = useCallback(async (id) => {
    const st = S.current
    setState('preparing')
    try {
      while (id === st.id) {
        if (st.queue.length === 0) {
          if (st.closed) break
          await new Promise((r) => { st.wake = r })
          continue
        }
        const item = st.queue.shift()
        ensure(item); ensure(st.queue[0]); ensure(st.queue[1])
        const blob = await item.promise
        if (id !== st.id) return
        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        st.audio = audio
        await new Promise((resolve) => {
          st.endPlay = resolve
          audio.onplaying = () => { if (id === st.id) setState('speaking') }
          audio.onended = resolve
          audio.onerror = resolve
          audio.play().catch(resolve)
        })
        URL.revokeObjectURL(url)
        st.audio = null
        st.endPlay = null
        if (id !== st.id) return
        setState('preparing')
      }
    } catch (e) {
      if (id === st.id) {
        st.failed = true
        st.queue = []
        st.closed = true
        errRef.current?.(`Voice unavailable (showing text only): ${e.message}`)
      }
    } finally {
      if (id === st.id) setState('idle')
    }
  }, [])

  const enqueue = useCallback((text) => {
    const st = S.current
    for (const part of splitLong(text)) {
      const item = { text: part, promise: null }
      st.queue.push(item)
      if (st.queue.length <= 2) ensure(item)
    }
    poke(st)
    if (st.runId !== st.id) { st.runId = st.id; run(st.id) }
  }, [run])

  const addSentence = useCallback((s) => {
    const st = S.current
    st.carry = st.carry ? `${st.carry} ${s}` : s
    if (st.carry.length >= MIN_CHARS) { const t = st.carry; st.carry = ''; enqueue(t) }
  }, [enqueue])

  const stop = useCallback(() => {
    const st = S.current
    st.id += 1
    st.queue = []; st.buffer = ''; st.carry = ''; st.closed = true
    if (st.audio) { st.audio.pause(); st.audio = null }
    if (st.endPlay) { st.endPlay(); st.endPlay = null }
    poke(st)
    setState('idle')
  }, [])

  const startStream = useCallback(() => {
    stop()
    const st = S.current
    st.closed = false
    st.failed = false
  }, [stop])

  const feed = useCallback((chunk) => {
    const st = S.current
    if (st.closed || st.failed) return
    st.buffer += chunk
    const [sentences, rest] = takeSentences(st.buffer, false)
    st.buffer = rest
    sentences.forEach(addSentence)
  }, [addSentence])

  const finish = useCallback(() => {
    const st = S.current
    if (st.closed) return
    const [sentences] = takeSentences(st.buffer, true)
    st.buffer = ''
    sentences.forEach(addSentence)
    if (st.carry) { const t = st.carry; st.carry = ''; enqueue(t) }
    st.closed = true
    poke(st)
    if (st.runId !== st.id) setState('idle') // nothing was ever queued
  }, [addSentence, enqueue])

  const speak = useCallback((text) => {
    startStream()
    feed(text)
    finish()
  }, [startStream, feed, finish])

  useEffect(() => stop, [stop])

  return { state, speaking: state === 'speaking', startStream, feed, finish, speak, stop }
}
