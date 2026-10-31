const OPTIONS = [
  { id: 'auto', label: 'Auto' },
  { id: 'en', label: 'English' },
  { id: 'ta', label: 'தமிழ்' },
]

export default function LanguageSelect({ value, onChange }) {
  return (
    <div className="inline-flex rounded-lg border border-stone-300 bg-white p-0.5 text-sm">
      {OPTIONS.map((o) => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          className={`rounded-md px-3 py-1 transition-colors ${
            value === o.id ? 'bg-stone-900 text-white' : 'text-stone-600 hover:bg-stone-100'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
