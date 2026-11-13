import { useEffect, useRef, useState } from 'react'
import { ArrowUpDown, ChevronLeft, ChevronRight, Hotel, ImageOff, Plane, Ticket, X } from 'lucide-react'
import { paginate } from '../lib/paginate'

export const TYPE_META = {
  flight: { label: 'Flight', plural: 'Flights', icon: Plane, color: 'bg-sky-100 text-sky-800' },
  hotel: { label: 'Stay', plural: 'Stays', icon: Hotel, color: 'bg-amber-100 text-amber-800' },
  transfer: { label: 'Transfer', plural: 'Transfers', icon: ArrowUpDown, color: 'bg-emerald-100 text-emerald-800' },
  attraction: { label: 'Experience', plural: 'Experiences', icon: Ticket, color: 'bg-rose-100 text-rose-800' },
}

export function TypeBadge({ type }) {
  const { label, icon: Icon, color } = TYPE_META[type]
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${color}`}><Icon size={13} />{label}</span>
}

export const Spinner = ({ label = 'Loading…' }) => <div role="status" className="flex items-center gap-3 p-6 text-muted"><span className="loading loading-spinner" />{label}</div>

export function Img({ src, alt = '', className = '' }) {
  const [bad, setBad] = useState(false)
  useEffect(() => setBad(false), [src])
  if (!src || bad) return <div className={`flex items-center justify-center bg-slate-100 text-slate-400 ${className}`}><ImageOff size={22} aria-label="No photo" /></div>
  return <img src={src} alt={alt} loading="lazy" onError={() => setBad(true)} className={`object-cover ${className}`} />
}

export function Pagination({ page, pages, onPage }) {
  if (pages <= 1) return null
  return <nav aria-label="Pagination" className="mt-4 flex items-center justify-center gap-3 text-sm">
    <button className="btn btn-sm btn-ghost" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft size={16} /></button>
    <span>Page {page} of {pages}</span>
    <button className="btn btn-sm btn-ghost" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight size={16} /></button>
  </nav>
}

// Paginates `items`; `render(item)` draws each one.
export function Paginated({ items, size = 3, render, className = 'grid gap-4' }) {
  const [page, setPage] = useState(1)
  const p = paginate(items, page, size)
  return <>
    <div className={className}>{p.items.map(render)}</div>
    <Pagination page={p.page} pages={p.pages} onPage={setPage} />
  </>
}

// Right-hand sheet built on <dialog>: Esc, focus trap and backdrop come from the browser.
export function Drawer({ title, onClose, children, wide }) {
  const ref = useRef(null)
  useEffect(() => { ref.current?.showModal() }, [])
  return <dialog ref={ref} onClose={onClose} onClick={e => e.target === ref.current && onClose()}
    className="m-0 ml-auto h-dvh max-h-none w-full max-w-none bg-white p-0 backdrop:bg-black/50 sm:w-[28rem] open:flex open:flex-col" style={wide ? { width: 'min(44rem,100%)' } : undefined}>
    <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
      <h2 className="text-lg font-bold">{title}</h2>
      <button className="btn btn-sm btn-circle btn-ghost" onClick={onClose} aria-label="Close"><X size={18} /></button>
    </header>
    <div className="flex-1 overflow-y-auto p-5">{children}</div>
  </dialog>
}

export function Modal({ onClose, children, label }) {
  const ref = useRef(null)
  useEffect(() => { ref.current?.showModal() }, [])
  return <dialog ref={ref} onClose={onClose} aria-label={label} onClick={e => e.target === ref.current && onClose()}
    className="m-auto w-[min(34rem,calc(100%-2rem))] rounded-2xl bg-white p-0 shadow-2xl backdrop:bg-black/50">
    {children}
  </dialog>
}
