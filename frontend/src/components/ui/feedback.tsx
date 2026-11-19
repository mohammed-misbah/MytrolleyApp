import { Loader2, AlertCircle, Inbox, RefreshCw } from 'lucide-react'
import { Button } from './button'

export function Spinner({ className = '' }: { className?: string }) {
  return <Loader2 className={`h-4 w-4 animate-spin ${className}`} aria-hidden />
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-[var(--text-2)]">
      <Spinner /> {label}
    </div>
  )
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <div
        className="flex h-14 w-14 items-center justify-center rounded-full"
        style={{ background: 'var(--chip-warm-bg)', color: 'var(--chip-warm-icon)' }}
      >
        <Inbox className="h-6 w-6" strokeWidth={1.8} />
      </div>
      <p className="text-[15px] font-semibold text-[var(--text-1)]">{title}</p>
      {description && <p className="max-w-sm text-[13px] text-[var(--text-2)]">{description}</p>}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 rounded-[14px] py-10 text-center"
      style={{ background: 'var(--danger-bg)', border: '1px solid rgba(199,62,62,.2)', color: 'var(--danger-text)' }}
    >
      <AlertCircle className="h-6 w-6" strokeWidth={1.8} />
      <p className="text-sm font-medium">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.8} /> Retry
        </Button>
      )}
    </div>
  )
}
