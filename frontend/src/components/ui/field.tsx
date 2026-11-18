import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { cn } from '@/utils/cn'

const base =
  'w-full rounded-control border border-line bg-white px-3 py-2 text-sm text-ink placeholder:text-subtle/70 focus:border-forest focus:outline-none focus:ring-2 focus:ring-lime/60 disabled:cursor-not-allowed disabled:bg-muted'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => <input ref={ref} className={cn(base, className)} {...props} />,
)
Input.displayName = 'Input'

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => <select ref={ref} className={cn(base, className)} {...props} />,
)
Select.displayName = 'Select'

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => <textarea ref={ref} className={cn(base, 'min-h-24', className)} {...props} />,
)
Textarea.displayName = 'Textarea'

export function Field({
  label,
  error,
  hint,
  children,
}: {
  label: string
  error?: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-subtle">{label}</span>
      {children}
      {hint && !error && <span className="block text-xs text-subtle">{hint}</span>}
      {error && <span className="block text-xs font-medium text-danger">{error}</span>}
    </label>
  )
}
