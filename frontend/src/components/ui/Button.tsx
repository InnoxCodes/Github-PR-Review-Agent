import type { ComponentProps } from 'react'
import { cn } from '@/lib/cn'

const variants = {
  primary:
    'bg-accent text-accent-fg shadow-[inset_0_1px_0_rgb(255_255_255/0.28)] hover:bg-accent-strong hover:shadow-glow',
  secondary: 'border border-line-strong bg-raised text-fg hover:bg-muted',
  outline: 'border border-line-strong text-fg hover:bg-muted',
  ghost: 'text-fg-muted hover:bg-muted hover:text-fg',
  danger: 'border border-line text-critical-text hover:border-critical/40 hover:bg-critical-soft',
} as const

const sizes = {
  sm: 'h-8 gap-1.5 rounded-md px-2.5 text-[13px]',
  md: 'h-10 gap-2 rounded-lg px-4 text-sm',
  lg: 'h-12 gap-2 rounded-xl px-5 text-[15px]',
  icon: 'size-9 rounded-lg',
  'icon-sm': 'size-8 rounded-md',
} as const

export type ButtonVariant = keyof typeof variants
export type ButtonSize = keyof typeof sizes

export function buttonClasses(variant: ButtonVariant = 'secondary', size: ButtonSize = 'md', className?: string) {
  return cn(
    'inline-flex shrink-0 select-none items-center justify-center whitespace-nowrap font-medium',
    'transition-[background-color,color,border-color,box-shadow,transform,opacity] duration-200 ease-out',
    'active:translate-y-px disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0',
    variants[variant],
    sizes[size],
    className,
  )
}

export interface ButtonProps extends ComponentProps<'button'> {
  variant?: ButtonVariant
  size?: ButtonSize
}

export function Button({ variant, size, className, type = 'button', ...props }: ButtonProps) {
  return <button type={type} className={buttonClasses(variant, size, className)} {...props} />
}
