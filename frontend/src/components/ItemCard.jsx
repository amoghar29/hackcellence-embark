import { Car, Clock, Pencil, Star, TriangleAlert } from 'lucide-react'
import { legOf } from '../lib/legs'
import { Img, TypeBadge } from './ui'
import { API } from '../lib/api'
import { duration, fmtDate, fmtTime, imageUrl, money } from '../lib/format'

export function itemFacts(it) {
  const d = it.details || {}
  switch (it.type) {
    case 'flight': return [`${d.airline} ${d.flight_number}`, `${d.from_airport} → ${d.to_airport}`, d.stops ? `${d.stops} stop${d.stops > 1 ? 's' : ''}` : 'Non-stop', duration(d.duration_minutes)]
    case 'hotel': return [`${d.area}`, '★'.repeat(d.stars || 0), d.rating && `${d.rating} rating`, `${d.room_name} × ${d.rooms}`, `${d.nights} night${d.nights > 1 ? 's' : ''}`].filter(Boolean)
    case 'transfer': return [d.transfer_type?.replaceAll('_', ' ').toLowerCase(), `${d.from_point} → ${d.to_point}`, duration(d.duration_minutes)]
    default: return [d.category, `${d.visit_minutes} min`, d.child_friendly && 'Good with kids'].filter(Boolean)
  }
}

export function when(it) {
  if (it.type === 'hotel') return `${fmtDate(it.start)} → ${fmtDate(it.end)}`
  const endDay = it.end?.slice(0, 10) !== it.start?.slice(0, 10) ? `${fmtDate(it.end)}, ` : ''
  return `${fmtDate(it.start)}, ${fmtTime(it.start)} → ${endDay}${fmtTime(it.end)}`
}

export default function ItemCard({ item, onOpen, onChange, canChange, updated }) {
  const hasPhoto = item.type === 'hotel' || item.type === 'attraction'
  return <article className={`flex flex-col overflow-hidden rounded-2xl border bg-white sm:flex-row ${updated ? 'border-emerald-400 ring-2 ring-emerald-200' : 'border-slate-200'}`}>
    {hasPhoto && <button onClick={() => onOpen(item)} className="h-44 shrink-0 sm:h-auto sm:w-48" aria-label={`Photos and details of ${item.name}`}>
      <Img src={imageUrl(item.details?.image, API)} alt="" className="h-full w-full" />
    </button>}
    <div className="flex flex-1 flex-col gap-2 p-4">
      <div className="flex items-center justify-between gap-2">
        <TypeBadge type={item.type} />
        {updated && <span className="badge badge-success badge-soft">Updated</span>}
        <span className="text-sm text-slate-500">{item.city}</span>
      </div>
      <h3 className="text-lg font-bold leading-tight">{item.name}</h3>
      <p className="flex items-center gap-1 text-sm text-slate-600"><Clock size={14} />{when(item)}</p>
      {(() => { const l = legOf(item); return l && <p className="flex flex-wrap items-center gap-x-2 text-xs text-slate-500"><Car size={13} />~{duration(l.minutes)} from {l.from} · {l.km} km
        {l.estimate && <span className="badge badge-ghost badge-xs">estimate</span>}
        <a href={l.link} target="_blank" rel="noreferrer" className="link link-primary">Directions</a></p> })()}
      <p className="flex flex-wrap gap-x-3 text-sm text-slate-600">{itemFacts(item).map((f, i) => <span key={i} className="flex items-center gap-1">{f.includes('rating') && <Star size={13} className="text-amber-500" />}{f}</span>)}</p>
      {item.warnings?.length > 0 && <ul className="rounded-lg bg-amber-50 p-2 text-sm text-amber-900">{item.warnings.map((w, i) => <li key={i} className="flex gap-2"><TriangleAlert size={15} className="mt-0.5 shrink-0" />{typeof w === 'string' ? w : w.message}</li>)}</ul>}
      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-2">
        <b className="text-lg">{money(item.price_inr)}</b>
        <div className="flex gap-2">
          {canChange && item.type !== 'transfer' && <button className="btn btn-sm btn-outline" onClick={() => onChange(item)}><Pencil size={14} />{item.type === 'attraction' ? 'Remove' : 'Change'}</button>}
          <button className="btn btn-sm btn-primary" onClick={() => onOpen(item)}>Details</button>
        </div>
      </div>
    </div>
  </article>
}
