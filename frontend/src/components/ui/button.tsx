import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/utils/cn'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-[14px] text-sm font-medium transition-[filter,background-color] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(47,191,139,.5)] disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'text-white hover:brightness-110',
        accent: 'text-white hover:brightness-110',
        outline: 'border text-[var(--text-1)] hover:bg-[var(--tile)]',
        ghost: 'text-[var(--text-2)] hover:bg-[var(--tile)] hover:text-[var(--text-1)]',
        danger: 'text-white hover:brightness-110',
      },
      size: {
        sm: 'h-8 px-3 text-xs',
        md: 'h-10 px-4',
        lg: 'h-11 px-6',
        icon: 'h-[34px] w-[34px]',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

const variantStyle: Record<string, React.CSSProperties> = {
  primary: { background: 'var(--brand-dark)', boxShadow: 'var(--brand-dark-shadow)' },
  accent: { background: 'var(--brand-dark)', boxShadow: 'var(--brand-dark-shadow)' },
  outline: { background: 'var(--card)', borderColor: 'rgba(18,45,32,.14)' },
  ghost: {},
  danger: { background: '#C73E3E' },
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
