import { cn } from '../../lib/cn'

export function Card({ className, ...props }) { return <div className={cn('card bg-base-100', className)} {...props} /> }
export function CardContent({ className, ...props }) { return <div className={cn('card-body', className)} {...props} /> }
