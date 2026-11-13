import { useEffect, useState } from 'react'
import { CircleAlert, TriangleAlert } from 'lucide-react'
import { Drawer, Img, Paginated, Spinner } from './ui'
import { dayFull } from '../lib/day'
import { API, change, getChangeOptions } from '../lib/api'
import { fmtDate, fmtTime, imageUrl, money } from '../lib/format'

// Add an experience on a chosen day: pick a day, pick a visit, see the new total, confirm.
// A visit that clashes with another or breaks a rule is refused with the reason and nothing changes.
export default function AddAttractionDrawer({ pkg, date, onClose, onChanged }) {
  const days = pkg.days.filter(d => d.date >= pkg.start_date && d.date <= pkg.end_date).map(d => d.date)
  const [day, setDay] = useState(days.includes(date) ? date : days[0])
  const [opts, setOpts] = useState(null)
  const [pick, setPick] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const full = dayFull(pkg, day)

  useEffect(() => {
    setOpts(null); setPick(null)
    getChangeOptions(pkg, 'attraction', { date: day }).then(r => setOpts(r.options)).catch(e => setErr({ error: e.error }))
  }, [day])

  async function add(o) {
    setBusy(true); setErr(null)
    try { onChanged(await change(pkg, { action: 'add_attraction', attraction_id: o.attraction_id, start: o.start })) }
    catch (e) { setErr(e); setPick(null) } finally { setBusy(false) }
  }

  return <Drawer title="Add an experience" onClose={onClose}>
    <label className="mb-4 block text-sm font-semibold">Day
      <select className="select select-bordered mt-1 w-full" value={day} onChange={e => { setDay(e.target.value); setErr(null) }}>
        {days.map(d => <option key={d} value={d}>{fmtDate(d)}</option>)}</select></label>
    {err && <div role="alert" className="alert alert-error mb-4 items-start text-sm"><CircleAlert size={18} />
      <div><p className="font-semibold">{err.code === 'CHANGE_REFUSED' ? "That can't be added" : 'Could not add'}</p>
        <ul className="list-disc pl-4">{(err.reasons?.length ? err.reasons : [err.error]).map((r, i) => <li key={i}>{r}</li>)}</ul>
        <p className="mt-1">Your trip is unchanged.</p></div></div>}
    {!opts ? <Spinner label="Finding things to do…" /> : opts.length === 0 ? <p className="text-slate-600">Nothing else is open on this day.</p> :
      <Paginated key={day} items={opts} size={4} render={o => {
        const newTotal = pkg.total_inr + o.price_inr, over = newTotal > pkg.budget_inr, sel = pick?.attraction_id === o.attraction_id
        return <article key={o.attraction_id} className="rounded-xl border border-slate-200 p-3">
          <div className="flex gap-3">
            <Img src={imageUrl(o.image, API)} className="h-20 w-24 shrink-0 rounded-lg" />
            <div className="min-w-0 flex-1"><h3 className="font-semibold leading-tight">{o.name}</h3>
              <p className="text-sm text-slate-600">{o.category} · {fmtTime(o.start)}–{fmtTime(o.end)}</p>
              {pkg.traveler.children > 0 && o.child_friendly === false && <span className="badge badge-warning badge-soft badge-sm mt-1">Not child friendly</span>}</div>
          </div>
          <div className="mt-2 flex items-center justify-between"><span><b>+{money(o.price_inr)}</b></span>
            <span title={full ? 'Remove 1 to add another' : undefined}>
              <button className="btn btn-sm btn-outline" disabled={full} onClick={() => { setPick(o); setErr(null) }}>Select</button></span></div>
          {sel && <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
            <p>New trip total <b>{money(newTotal)}</b> <span className="text-slate-500">(was {money(pkg.total_inr)})</span></p>
            {over && <p className="mt-1 flex items-center gap-1 text-amber-700"><TriangleAlert size={14} />This goes {money(newTotal - pkg.budget_inr)} over your budget.</p>}
            <div className="mt-2 flex gap-2"><button className="btn btn-sm flex-1" onClick={() => setPick(null)}>Cancel</button>
              <button className="btn btn-sm btn-primary flex-1" disabled={busy} onClick={() => add(o)}>{busy ? 'Adding…' : 'Add to trip'}</button></div>
          </div>}
        </article>
      }} />}
  </Drawer>
}
