import { useCallback, useEffect, useState } from 'react'
import { Brain, Plus, Trash2 } from 'lucide-react'
import { api, fmtDate } from '../services/api'
import PageHeader, { Button, Empty, Toggle } from '../components/PageHeader'

export default function Memory({ settings, updateSettings }) {
  const [items, setItems] = useState([])
  const [text, setText] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    api.get('/memories').then((d) => { setItems(d); setError(null) })
      .catch((e) => setError(e.message)).finally(() => setLoading(false))
  }, [])
  useEffect(() => { load() }, [load])

  const add = async () => {
    if (text.trim().length < 3) return
    try { await api.post('/memories', { text }); setText(''); load() } catch (e) { setError(e.message) }
  }
  const remove = async (id) => { await api.del(`/memories/${id}`); setItems((x) => x.filter((m) => m.id !== id)) }
  const clearAll = async () => {
    if (window.confirm('Delete ALL saved memories? This cannot be undone.')) { await api.del('/memories'); load() }
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Memory" subtitle="Long-term facts Vaani remembers, stored locally in Qdrant.">
        <Button variant="danger" onClick={clearAll} disabled={!items.length}><Trash2 size={16} /> Clear all</Button>
      </PageHeader>
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {settings && (
            <div className="divide-y divide-stone-200 rounded-xl border border-stone-200 bg-white px-4">
              <Toggle checked={settings.use_memory} onChange={(v) => updateSettings({ use_memory: v })}
                label="Use memories in replies" hint="Retrieve relevant memories before answering." />
              <Toggle checked={settings.auto_memory} onChange={(v) => updateSettings({ auto_memory: v })}
                label="Save useful facts automatically" hint="Only durable facts and preferences are kept, never whole conversations." />
            </div>
          )}
          <div className="flex gap-2">
            <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && add()}
              placeholder="Add a memory, e.g. “The user is vegetarian.”"
              className="flex-1 rounded-lg border border-stone-300 bg-white px-3.5 py-2 text-sm outline-none focus:border-stone-500" />
            <Button onClick={add}><Plus size={16} /> Add</Button>
          </div>
          {error && <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm text-rose-800">{error}</p>}
          {!loading && !items.length && !error && <Empty icon={Brain} text="No memories yet. Tell Vaani something about yourself." />}
          <ul className="divide-y divide-stone-200 rounded-xl border border-stone-200 bg-white empty:hidden">
            {items.map((m) => (
              <li key={m.id} className="flex items-start gap-3 px-4 py-3">
                <div className="flex-1">
                  <div className="text-sm">{m.text}</div>
                  <div className="mt-0.5 text-xs text-stone-500">{m.source === 'user' ? 'Added by you' : 'Learned automatically'} · {fmtDate(m.created_at)}</div>
                </div>
                <button onClick={() => remove(m.id)} title="Delete" className="rounded-md p-2 text-stone-400 hover:bg-rose-50 hover:text-rose-700"><Trash2 size={16} /></button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
