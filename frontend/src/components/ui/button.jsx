import { cn } from '../../lib/cn'

const styles = { default: 'btn-primary', secondary: 'btn-secondary', outline: 'btn-outline', ghost: 'btn-ghost', soft: 'btn-soft' }
export function Button({ variant = 'default', size = 'md', className, type = 'button', ...props }) {
  return <button type={type} className={cn('btn rounded-xl normal-case font-semibold', styles[variant] || styles.default, size === 'sm' && 'btn-sm', size === 'lg' && 'btn-lg', className)} {...props} />
}
