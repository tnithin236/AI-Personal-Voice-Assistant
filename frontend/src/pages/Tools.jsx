import { useEffect, useState } from 'react'
import { Play, ShieldAlert } from 'lucide-react'
import { api } from '../services/api'
import PageHeader, { Button, Toggle } from '../components/PageHeader'

function ToolCard({ tool }) {
  const [args, setArgs] = useState({})
  const [result, setResult] = useState(null)
  const [pending, setPending] = useState(null)
  const [busy, setBusy] = useState(false)

  const run = async () => {
    setBusy(true); setResult(null)
    try {
      const res = await api.post('/tools/run', { tool: tool.name, args })
      if (res.pending_action) setPending(res.pending_action)
      else setResult({ ok: true, text: res.result })
    } catch (e) { setResult({ ok: false, text: e.message }) }
    setBusy(false)
  }
  const confirm = async (approve) => {
    try { const r = await api.post(`/actions/${pending.id}/confirm`, { approve }); setResult({ ok: true, text: r.text }) }
    catch (e) { setResult({ ok: false, text: e.message }) }
    setPending(null)
  }

  return (
    <div className="rounded-xl border border-stone-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            {tool.name.replace('_', ' ')}
            {tool.sensitive && <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800"><ShieldAlert size={11} /> asks first</span>}
          </div>
          <p className="mt-0.5 text-sm text-stone-500">{tool.description}</p>
        </div>
        <Button variant="ghost" onClick={run} disabled={busy}><Play size={14} /> Run</Button>
      </div>
      {Object.entries(tool.params).map(([k, hint]) => (
        <input key={k} placeholder={`${k} — ${hint}`} value={args[k] || ''}
          onChange={(e) => setArgs({ ...args, [k]: e.target.value })}
          onKeyDown={(e) => e.key === 'Enter' && run()}
          className="mt-3 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-stone-500" />
      ))}
      {pending && (
        <div className="mt-3 flex items-center gap-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm">
          <span className="flex-1 text-amber-900">Confirm: {pending.description}</span>
          <Button variant="ghost" onClick={() => confirm(false)}>Deny</Button>
          <Button onClick={() => confirm(true)}>Approve</Button>
        </div>
      )}
      {result && (
        <pre className={`mt-3 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg px-3 py-2 text-xs ${result.ok ? 'bg-stone-100 text-stone-800' : 'bg-rose-50 text-rose-800'}`}>{result.text}</pre>
      )}
    </div>
  )
}

export default function Tools({ settings, updateSettings }) {
  const [tools, setTools] = useState([])
  const [error, setError] = useState(null)
  useEffect(() => { api.get('/tools').then(setTools).catch((e) => setError(e.message)) }, [])
  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Tools" subtitle="What the assistant can do on request. You can also run any tool by hand here." />
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {settings && (
            <div className="divide-y divide-stone-200 rounded-xl border border-stone-200 bg-white px-4">
              <Toggle checked={settings.use_tools} onChange={(v) => updateSettings({ use_tools: v })}
                label="Let the assistant use tools" hint="Calculator, web search, file search, desktop actions." />
              <Toggle checked={settings.confirm_all_actions} onChange={(v) => updateSettings({ confirm_all_actions: v })}
                label="Confirm every desktop action" hint="Deleting always asks for confirmation. Turn this on to also confirm opening apps, websites, folders and key presses." />
            </div>
          )}
          {error && <p className="text-sm text-rose-700">{error}</p>}
          {tools.map((t) => <ToolCard key={t.name} tool={t} />)}
        </div>
      </div>
    </div>
  )
}
