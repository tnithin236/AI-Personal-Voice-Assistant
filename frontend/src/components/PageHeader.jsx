export default function PageHeader({ title, subtitle, children }) {
  return (
    <header className="flex items-center justify-between border-b border-stone-200 px-8 py-5">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-stone-500">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2">{children}</div>
    </header>
  )
}

export function Button({ children, variant = 'default', className = '', ...props }) {
  const styles = {
    default: 'bg-stone-900 text-white hover:bg-stone-700',
    ghost: 'border border-stone-300 bg-white text-stone-700 hover:bg-stone-100',
    danger: 'border border-rose-200 bg-white text-rose-700 hover:bg-rose-50',
  }
  return (
    <button
      {...props}
      className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors disabled:opacity-40 ${styles[variant]} ${className}`}
    >
      {children}
    </button>
  )
}

export function Empty({ icon: Icon, text }) {
  return (
    <div className="flex flex-col items-center gap-3 py-24 text-stone-400">
      <Icon size={28} strokeWidth={1.5} />
      <p className="text-sm">{text}</p>
    </div>
  )
}

export function Toggle({ checked, onChange, label, hint }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-6 py-3">
      <span>
        <span className="block text-sm font-medium">{label}</span>
        {hint && <span className="block text-xs text-stone-500">{hint}</span>}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${checked ? 'bg-stone-900' : 'bg-stone-300'}`}
      >
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${checked ? 'left-[22px]' : 'left-0.5'}`} />
      </button>
    </label>
  )
}
