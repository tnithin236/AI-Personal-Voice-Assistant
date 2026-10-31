import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../services/api'

let keyCounter = 0
const nextKey = () => `k${++keyCounter}`

export const BUSY_STAGES = ['transcribing', 'retrieving', 'thinking', 'responding']

/** All real-time state for the assistant: WebSocket, messages, voice stage, pending confirmations. */
export function useAssistant({ onReply } = {}) {
  const [connected, setConnected] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [stage, setStage] = useState('idle')
  const [level, setLevel] = useState(0)
  const [pending, setPending] = useState(null)
  const [error, setError] = useState(null)
  const wsRef = useRef(null)
  const convRef = useRef(null)
  const replyRef = useRef(onReply)
  replyRef.current = onReply

  const handle = useCallback((ev) => {
    switch (ev.type) {
      case 'conversation':
        convRef.current = ev.id
        setConversationId(ev.id)
        break
      case 'status':
        setStage(ev.stage)
        if (ev.stage !== 'listening') setLevel(0)
        break
      case 'level':
        setLevel(ev.value)
        break
      case 'transcript':
        setMessages((m) => [...m, { key: nextKey(), role: 'user', content: ev.text, language: ev.language, voice: true }])
        break
      case 'token':
        setMessages((m) => {
          const last = m[m.length - 1]
          if (last && last.streaming) return [...m.slice(0, -1), { ...last, content: last.content + ev.text }]
          return [...m, { key: nextKey(), role: 'assistant', content: ev.text, streaming: true }]
        })
        break
      case 'pending_action':
        setPending(ev)
        break
      case 'done':
        setMessages((m) => {
          const final = { key: nextKey(), id: ev.message_id, role: 'assistant', content: ev.text,
            language: ev.language, tool: ev.tool, timings: ev.timings }
          const last = m[m.length - 1]
          return last && last.streaming ? [...m.slice(0, -1), final] : [...m, final]
        })
        replyRef.current?.(ev)
        break
      case 'error':
        setError(ev.message)
        setMessages((m) => (m[m.length - 1]?.streaming && !m[m.length - 1].content ? m.slice(0, -1) : m))
        break
      case 'cancelled':
        setMessages((m) => m.map((x) => (x.streaming ? { ...x, streaming: false } : x)))
        break
      default:
    }
  }, [])

  useEffect(() => {
    let alive = true
    let timer
    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws`)
      wsRef.current = ws
      ws.onopen = () => alive && setConnected(true)
      ws.onmessage = (e) => { try { handle(JSON.parse(e.data)) } catch { /* ignore malformed */ } }
      ws.onclose = () => {
        if (!alive) return
        setConnected(false)
        setStage('idle')
        timer = setTimeout(connect, 1500)
      }
    }
    connect()
    return () => { alive = false; clearTimeout(timer); wsRef.current?.close() }
  }, [handle])

  const send = useCallback((payload) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setError('Not connected to the backend. Is it running on port 8000?')
      return false
    }
    ws.send(JSON.stringify({ conversation_id: convRef.current, ...payload }))
    return true
  }, [])

  const sendText = useCallback((text) => {
    const t = text.trim()
    if (!t) return
    if (send({ type: 'chat', text: t })) {
      setError(null)
      setStage('thinking')
      setMessages((m) => [...m, { key: nextKey(), role: 'user', content: t }])
    }
  }, [send])

  const startVoice = useCallback(() => { setError(null); send({ type: 'voice_start' }) }, [send])
  const stopVoice = useCallback(() => send({ type: 'voice_stop' }), [send])
  const cancel = useCallback(() => send({ type: 'cancel' }), [send])

  const regenerate = useCallback(() => {
    if (!convRef.current) return
    setMessages((m) => (m[m.length - 1]?.role === 'assistant' ? m.slice(0, -1) : m))
    if (send({ type: 'regenerate' })) setStage('thinking')
  }, [send])

  const newConversation = useCallback(() => {
    send({ type: 'cancel' })
    convRef.current = null
    setConversationId(null)
    setMessages([])
    setPending(null)
    setError(null)
  }, [send])

  const loadConversation = useCallback(async (id) => {
    const conv = await api.get(`/conversations/${id}`)
    convRef.current = id
    setConversationId(id)
    setPending(null)
    setError(null)
    setMessages(conv.messages.map((m) => ({
      key: nextKey(), id: m.id, role: m.role, content: m.content, language: m.language,
      tool: m.meta?.tool, timings: m.meta?.timings,
    })))
  }, [])

  const clearConversation = useCallback(async () => {
    if (convRef.current) await api.post(`/conversations/${convRef.current}/clear`)
    setMessages([])
    setPending(null)
  }, [])

  const confirmAction = useCallback(async (approve) => {
    if (!pending) return
    try {
      const res = await api.post(`/actions/${pending.id}/confirm`, { approve })
      setMessages((m) => [...m, { key: nextKey(), id: res.message_id, role: 'assistant', content: res.text }])
    } catch (e) {
      setError(e.message)
    }
    setPending(null)
  }, [pending])

  return {
    connected, conversationId, messages, stage, level, pending, error, setError,
    sendText, startVoice, stopVoice, cancel, regenerate, newConversation,
    loadConversation, clearConversation, confirmAction,
  }
}
