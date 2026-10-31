async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch { /* not JSON */ }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  const type = res.headers.get('content-type') || ''
  return type.includes('application/json') ? res.json() : res
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const api = {
  get: (path) => fetch('/api' + path).then(handle),
  post: (path, body) => fetch('/api' + path, json('POST', body ?? {})).then(handle),
  put: (path, body) => fetch('/api' + path, json('PUT', body)).then(handle),
  del: (path) => fetch('/api' + path, { method: 'DELETE' }).then(handle),
  upload: (path, file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch('/api' + path, { method: 'POST', body: form }).then(handle)
  },
  tts: async (text, language) => {
    const res = await fetch('/api/tts', json('POST', { text, language }))
    if (!res.ok) await handle(res)
    return res.blob()
  },
}

export const fmtDate = (ts) =>
  new Date(ts * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })

export const fmtBytes = (n) =>
  n > 2 ** 20 ? `${(n / 2 ** 20).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`
