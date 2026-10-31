import { useCallback, useEffect, useRef, useState } from 'react'
import { FileText, Loader2, Trash2, Upload } from 'lucide-react'
import { api, fmtBytes, fmtDate } from '../services/api'
import PageHeader, { Empty, Toggle } from '../components/PageHeader'

export default function Documents({ settings, updateSettings }) {
  const [docs, setDocs] = useState([])
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [drag, setDrag] = useState(false)
  const input = useRef(null)

  const load = useCallback(() => api.get('/documents').then(setDocs).catch((e) => setError(e.message)), [])
  useEffect(() => { load() }, [load])

  const upload = async (files) => {
    setError(null)
    for (const f of files) {
      setBusy(f.name)
      try { await api.upload('/documents', f) } catch (e) { setError(`${f.name}: ${e.message}`) }
    }
    setBusy(null)
    load()
  }
  const remove = async (id) => { await api.del(`/documents/${id}`); load() }

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Documents" subtitle="Upload PDF, TXT or Markdown files. Vaani answers from them and says when it can't find something." />
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {settings && (
            <div className="rounded-xl border border-stone-200 bg-white px-4">
              <Toggle checked={settings.use_documents} onChange={(v) => updateSettings({ use_documents: v })}
                label="Use documents in replies" hint="Search uploaded documents for relevant passages before answering." />
            </div>
          )}
          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); upload([...e.dataTransfer.files]) }}
            onClick={() => input.current?.click()}
            className={`flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${drag ? 'border-stone-500 bg-stone-100' : 'border-stone-300 bg-white hover:bg-stone-50'}`}
          >
            {busy ? <Loader2 className="animate-spin text-stone-500" /> : <Upload className="text-stone-400" />}
            <p className="text-sm font-medium">{busy ? `Indexing ${busy}…` : 'Drop files here or click to browse'}</p>
            <p className="text-xs text-stone-500">PDF, TXT, MD · up to 50 MB · text is extracted, chunked and embedded locally</p>
            <input ref={input} type="file" multiple accept=".pdf,.txt,.md" className="hidden"
              onChange={(e) => { upload([...e.target.files]); e.target.value = '' }} />
          </div>
          {error && <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm text-rose-800">{error}</p>}
          {docs.length === 0 ? <Empty icon={FileText} text="No documents indexed yet." /> : (
            <ul className="divide-y divide-stone-200 rounded-xl border border-stone-200 bg-white">
              {docs.map((d) => (
                <li key={d.id} className="flex items-center gap-3 px-4 py-3">
                  <FileText size={18} className="text-stone-400" />
                  <div className="flex-1">
                    <div className="text-sm font-medium">{d.filename}</div>
                    <div className="text-xs text-stone-500">{d.chunks} chunks{d.pages ? ` · ${d.pages} pages` : ''} · {fmtBytes(d.size_bytes)} · {fmtDate(d.created_at)}</div>
                  </div>
                  <button onClick={() => remove(d.id)} title="Delete" className="rounded-md p-2 text-stone-400 hover:bg-rose-50 hover:text-rose-700"><Trash2 size={16} /></button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
