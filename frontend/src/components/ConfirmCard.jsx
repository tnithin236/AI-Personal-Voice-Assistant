import { ShieldAlert } from 'lucide-react'
import { Button } from './PageHeader'

export default function ConfirmCard({ pending, onApprove, onDeny }) {
  return (
    <div className="mx-auto flex w-full max-w-3xl items-center gap-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3">
      <ShieldAlert className="shrink-0 text-amber-700" size={20} />
      <div className="flex-1 text-sm">
        <div className="font-medium text-amber-900">Confirmation required</div>
        <div className="text-amber-800">Vaani wants to {pending.description}.</div>
      </div>
      <Button variant="ghost" onClick={onDeny}>Deny</Button>
      <Button onClick={onApprove}>Approve</Button>
    </div>
  )
}
