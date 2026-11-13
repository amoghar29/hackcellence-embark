import { useEffect, useState } from 'react'
import { CircleAlert, TriangleAlert } from 'lucide-react'
import { Drawer, Img, Paginated, Spinner } from './ui'
import { API, change, getChangeOptions } from '../lib/api'
import { duration, fmtDate, fmtTime, imageUrl, money } from '../lib/format'

export const Diff = ({ v }) => v === 0 ? <span className="badge">Same price</span>
  : <span className={`badge ${v < 0 ? 'badge-success' : 'badge-warning'}`}>{v < 0 ? `Save ${money(-v)}` : `+${money(v)}`}</span>

// Pick an alternative -> see the new total -> confirm. A refused change shows why and leaves the trip as is.
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
  const bodyFor = o => isHotel ? { action: 'change_hotel', city: item.city, hotel_id: o.hotel_id, room_id: o.room_id } : { action: 'change_flight', item_id: item.item_id, flight_id: o.flight_id }
  const isCurrent = o => isHotel ? o.hotel_id === item.catalog_id && o.room_id === item.room_id : o.flight_id === item.catalog_id
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
    {!opts && !err ? <Spinner label="Finding alternatives…" /> : opts && <Paginated items={opts} size={4} render={o => {
      const newTotal = pkg.total_inr + o.price_diff_inr, over = newTotal > pkg.budget_inr, sel = pick && key(pick) === key(o)
      return <article key={key(o)} className={`rounded-xl border p-3 ${isCurrent(o) ? 'border-primary bg-brand-soft' : 'border-slate-200'}`}>
        <div className="flex gap-3">
          {isHotel && <Img src={imageUrl(o.image, API)} className="h-20 w-24 shrink-0 rounded-lg" />}
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold leading-tight">{isHotel ? o.name : `${o.airline} ${o.flight_number}`}</h3>
            <p className="text-sm text-slate-600">{isHotel ? `${o.area} · ${'★'.repeat(o.stars)} · ${o.rating} · ${o.room_type.toLowerCase()} × ${o.rooms}`
              : `${o.from_airport} ${fmtTime(o.departure)} → ${o.to_airport} ${fmtTime(o.arrival)} · ${o.stops ? `${o.stops} stop` : 'Non-stop'}`}</p>
            {isFlight && <p className="text-xs text-slate-500">{fmtDate(o.departure)}</p>}
          </div>
        </div>
        <div className="mt-2 flex items-center justify-between"><span><b>{money(o.price_inr)}</b> <Diff v={o.price_diff_inr} /></span>
          {isCurrent(o) ? <span className="badge badge-primary">Current</span> : <button className="btn btn-sm btn-outline" onClick={() => { setPick(o); setErr(null) }}>Select</button>}</div>
        {sel && <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
          <p>New trip total <b>{money(newTotal)}</b> <span className="text-slate-500">(was {money(pkg.total_inr)})</span></p>
          {over && <p className="mt-1 flex items-center gap-1 text-amber-700"><TriangleAlert size={14} />This goes {money(newTotal - pkg.budget_inr)} over your budget.</p>}
          <div className="mt-2 flex gap-2"><button className="btn btn-sm flex-1" onClick={() => setPick(null)}>Cancel</button>
            <button className="btn btn-sm btn-primary flex-1" disabled={busy} onClick={() => apply(bodyFor(o))}>{busy ? 'Updating…' : 'Confirm change'}</button></div>
        </div>}
      </article>
    }} />}
  </Drawer>
}
