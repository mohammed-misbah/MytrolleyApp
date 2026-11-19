import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/utils/cn'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-[13px] text-sm font-medium transition-[filter,background-color] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(234,122,59,.45)] disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'text-white hover:brightness-110',
        accent: 'text-white hover:brightness-110',
        outline: 'border text-[var(--text-1)] hover:bg-[var(--tile)]',
        ghost: 'text-[var(--text-1)] hover:bg-[var(--tile)]',
        danger: 'text-white hover:brightness-110',
      },
      size: {
        sm: 'h-8 px-3 text-xs',
        md: 'h-10 px-4',
        lg: 'h-11 px-6',
        icon: 'h-[34px] w-[34px] rounded-[10px]',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

const variantStyle: Record<string, React.CSSProperties> = {
  primary: { background: 'var(--dark)', boxShadow: 'var(--dark-shadow)' },
  accent: { background: 'var(--dark)', boxShadow: 'var(--dark-shadow)' },
  outline: { background: 'var(--card)', borderColor: 'rgba(45,30,15,.14)' },
  ghost: {},
  danger: { background: 'var(--danger)' },
}

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size, style, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      style={{ ...variantStyle[variant ?? 'primary'], ...style }}
      {...props}
    />
  ),
)
Button.displayName = 'Button'
