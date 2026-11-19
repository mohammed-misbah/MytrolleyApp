import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { cn } from '@/utils/cn'

const base =
  'w-full rounded-[13px] border px-3 py-2 text-[13.5px] text-[var(--text-1)] placeholder:text-[var(--text-3)] focus:outline-none focus:ring-[3px] focus:ring-[rgba(234,122,59,.15)] disabled:cursor-not-allowed disabled:opacity-50'

const baseStyle: React.CSSProperties = {
  background: 'var(--card)',
  borderColor: 'var(--line-input)',
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, style, ...props }, ref) => (
    <input ref={ref} className={cn(base, 'h-[46px]', className)} style={{ ...baseStyle, ...style }} {...props} />
  ),
)
Input.displayName = 'Input'

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, style, ...props }, ref) => (
    <select ref={ref} className={cn(base, 'h-[46px]', className)} style={{ ...baseStyle, ...style }} {...props} />
  ),
)
Select.displayName = 'Select'

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, style, ...props }, ref) => (
    <textarea ref={ref} className={cn(base, 'min-h-24', className)} style={{ ...baseStyle, ...style }} {...props} />
  ),
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
      <span className="text-[12.5px] font-semibold text-[var(--text-1)]">{label}</span>
      {children}
      {hint && !error && <span className="block text-xs text-[var(--text-2)]">{hint}</span>}
      {error && <span className="block text-xs font-medium text-[var(--danger)]">{error}</span>}
    </label>
  )
}
