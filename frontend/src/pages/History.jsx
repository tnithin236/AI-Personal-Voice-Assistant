import { useCallback, useEffect, useState } from 'react'
import { MessageSquare, Plus, Trash2 } from 'lucide-react'
import { api, fmtDate } from '../services/api'
import PageHeader, { Button, Empty } from '../components/PageHeader'

export default function History({ onOpen, onNew, activeId }) {
  const [items, setItems] = useState([])
  const [error, setError] = useState(null)
  const load = useCallback(() => api.get('/conversations').then(setItems).catch((e) => setError(e.message)), [])
  useEffect(() => { load() }, [load])

  const remove = async (id) => {
    await api.del(`/conversations/${id}`)
    if (id === activeId) onNew()
    load()
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Chat History" subtitle="Every conversation is stored locally in SQLite.">
        <Button onClick={onNew}><Plus size={16} /> New conversation</Button>
      </PageHeader>
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {error && <p className="mb-4 text-sm text-rose-700">{error}</p>}
        {items.length === 0 ? (
          <Empty icon={MessageSquare} text="No conversations yet." />
        ) : (
          <ul className="mx-auto max-w-3xl divide-y divide-stone-200 rounded-xl border border-stone-200 bg-white">
            {items.map((c) => (
              <li key={c.id} className="flex items-center gap-3 px-4 py-3 hover:bg-stone-50">
                <button onClick={() => onOpen(c.id)} className="flex-1 text-left">
                  <div className={`text-sm font-medium ${c.id === activeId ? 'text-teal-800' : ''}`}>{c.title}</div>
                  <div className="text-xs text-stone-500">{fmtDate(c.updated_at)} · {c.message_count} messages</div>
                </button>
                <button onClick={() => remove(c.id)} title="Delete" className="rounded-md p-2 text-stone-400 hover:bg-rose-50 hover:text-rose-700">
                  <Trash2 size={16} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
