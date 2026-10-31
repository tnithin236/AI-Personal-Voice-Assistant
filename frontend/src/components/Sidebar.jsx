import { Brain, FileText, MessageSquare, Mic, Settings as Cog, Wrench } from 'lucide-react'
import Logo from './Logo'

const ITEMS = [
  { id: 'assistant', label: 'Assistant', icon: Mic },
  { id: 'history', label: 'Chat History', icon: MessageSquare },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'documents', label: 'Documents', icon: FileText },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'settings', label: 'Settings', icon: Cog },
]

export default function Sidebar({ page, onNavigate, connected }) {
  return (
    <aside className="flex w-16 shrink-0 flex-col border-r border-stone-200 bg-white md:w-60">
      <div className="flex items-center gap-3 px-4 py-5">
        <Logo />
        <div className="hidden md:block">
          <div className="text-[15px] font-semibold leading-none tracking-tight">Vaani</div>
          <div className="mt-1 text-xs text-stone-500">Personal voice assistant</div>
        </div>
      </div>
      <nav className="mt-2 flex flex-1 flex-col gap-1 px-2">
        {ITEMS.map(({ id, label, icon: Icon }) => {
          const active = page === id
          return (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              title={label}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                active ? 'bg-stone-900 text-white' : 'text-stone-600 hover:bg-stone-100'
              }`}
            >
              <Icon size={18} strokeWidth={1.75} />
              <span className="hidden md:inline">{label}</span>
            </button>
          )
        })}
      </nav>
      <div className="flex items-center gap-2 px-4 py-4 text-xs text-stone-500">
        <span className={`h-2 w-2 rounded-full ${connected ? 'bg-teal-600' : 'bg-rose-500'}`} />
        <span className="hidden md:inline">{connected ? 'Backend connected' : 'Backend offline'}</span>
      </div>
    </aside>
  )
}
