import { useEffect, useState } from 'react'
import { CircleAlert, TriangleAlert } from 'lucide-react'
import { Drawer, Img, Paginated, Spinner } from './ui'
import { API, change, getChangeOptions } from '../lib/api'
import { duration, fmtDate, fmtTime, imageUrl, money } from '../lib/format'
import { changeSummary } from '../lib/trip'

export const Diff = ({ v }) => v === 0 ? <span className="badge">Same price</span>
  : <span className={`badge ${v < 0 ? 'badge-success' : 'badge-warning'}`}>{v < 0 ? `Save ${money(-v)}` : `+${money(v)}`}</span>

// What choosing an option does to the whole trip: items swapped or removed, notices, new total, budget.
export function Effects({ pkg, preview, rebuilt }) {
  const fx = changeSummary(pkg, preview), total = preview.total_inr
  const changed = rebuilt ? [] : fx.changed
  return <div className="mt-2 rounded-lg bg-slate-50 p-2 text-sm" aria-label="What this change affects">
    {(changed.length > 0 || preview.notices?.length > 0) && <ul className="mb-1 list-disc pl-4">
      {changed.map((c, i) => <li key={i}>{c.from && <s className="opacity-70">{c.from}</s>} {c.from && c.to && '→'} {c.to ?? 'removed'}</li>)}
      {(preview.notices || []).map((x, i) => <li key={`n${i}`} className="text-amber-800">{x.message}</li>)}</ul>}
    <p>New trip total <b>{money(total)}</b> <span className="text-slate-500">(was {money(pkg.total_inr)})</span></p>
    {total > pkg.budget_inr && <p className="mt-1 flex items-center gap-1 text-amber-700"><TriangleAlert size={14} />This goes {money(total - pkg.budget_inr)} over your budget.</p>}
  </div>
}

// Only alternatives the server accepts are listed, each with what it affects (its preview package) -> pick -> confirm. A refused change shows why and leaves the trip as is.
export default function ChangeDrawer({ pkg, item, onClose, onChanged }) {
  const [opts, setOpts] = useState(null)
  const [pick, setPick] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const isHotel = item.type === 'hotel', isFlight = item.type === 'flight', isAttr = item.type === 'attraction'

  useEffect(() => {
    if (isAttr) return
    getChangeOptions(pkg, item.type, isHotel ? { city: item.city } : { direction: item.details.direction })
      .then(r => setOpts(r.options)).catch(e => setErr({ error: e.error }))
  }, [])

  async function apply(body) {
    setBusy(true); setErr(null)
    try { onChanged(await change(pkg, body)) }
    catch (e) { setErr(e); setPick(null) } finally { setBusy(false) }
  }
  const key = o => isHotel ? o.room_id : o.flight_id

  const error = err && <div role="alert" className="alert alert-error mb-4 items-start text-sm"><CircleAlert size={18} />
    <div><p className="font-semibold">{err.code === 'CHANGE_REFUSED' ? "That change isn't possible" : 'Could not change'}</p>
      <ul className="list-disc pl-4">{(err.reasons?.length ? err.reasons : [err.error]).map((r, i) => <li key={i}>{r}</li>)}</ul>
      <p className="mt-1">Your trip is unchanged.</p></div></div>

  if (isAttr) return <Drawer title="Remove experience" onClose={onClose}>
    {error}
    <p>Remove <b>{item.name}</b> ({fmtDate(item.start)}) from your trip? Your total drops by {money(item.price_inr)}.</p>
    <div className="mt-5 flex gap-2"><button className="btn flex-1" onClick={onClose}>Keep it</button>
      <button className="btn btn-error flex-1" disabled={busy} onClick={() => apply({ action: 'remove_attraction', item_id: item.item_id })}>{busy ? 'Removing…' : 'Remove'}</button></div>
  </Drawer>

  return <Drawer title={isHotel ? `Change stay in ${item.city}` : `Change ${item.details.direction === 'RETURN' ? 'return' : 'arrival'} flight`} onClose={onClose}>
    <p className="mb-4 text-sm text-slate-600">Now: <b>{item.name}</b> · {money(item.price_inr)}. Prices show the difference to your trip total.</p>
    {error}
    {!opts && !err ? <Spinner label="Finding alternatives…" /> : opts && (opts.length === 0 ? <p className="text-slate-600">No other {isHotel ? 'stay' : 'flight'} works with the rest of your trip.</p>
      : <Paginated items={opts} size={4} render={o => {
      const sel = pick && key(pick) === key(o)
      return <article key={key(o)} className={`rounded-xl border p-3 ${sel ? 'border-primary' : 'border-slate-200'}`}>
        <div className="flex gap-3">
          {isHotel && <Img src={imageUrl(o.image, API)} className="h-20 w-24 shrink-0 rounded-lg" />}
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold leading-tight">{isHotel ? o.name : `${o.airline} ${o.flight_number}`}</h3>
            <p className="text-sm text-slate-600">{isHotel ? `${o.area} · ${'★'.repeat(o.stars)} · ${o.rating} · ${o.room_type.toLowerCase()} × ${o.rooms}`
              : `${o.from_airport} ${fmtTime(o.departure)} → ${o.to_airport} ${fmtTime(o.arrival)} · ${o.stops ? `${o.stops} stop` : 'Non-stop'}`}</p>
            {isFlight && <p className="text-xs text-slate-500">{fmtDate(o.departure)}</p>}
          </div>
        </div>
        <div className="mt-2 flex items-center justify-between"><span><b>{money(o.price_inr)}</b> <Diff v={o.preview.total_inr - pkg.total_inr} /></span>
          {!sel && <button className="btn btn-sm btn-outline" onClick={() => setPick(o)}>Select</button>}</div>
        <Effects pkg={pkg} preview={o.preview} />
        {sel && <div className="mt-2 flex gap-2"><button className="btn btn-sm flex-1" onClick={() => setPick(null)}>Cancel</button>
          <button className="btn btn-sm btn-primary flex-1" onClick={() => onChanged(o.preview)}>Confirm change</button></div>}
      </article>
    }} />)}
  </Drawer>
}
