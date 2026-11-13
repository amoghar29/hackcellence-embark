import { useEffect, useState } from 'react'
import { CircleAlert } from 'lucide-react'
import { Effects } from './ChangeDrawer'
import { Drawer, Img, Paginated, Spinner } from './ui'
import { dayFull } from '../lib/day'
import { API, getChangeOptions } from '../lib/api'
import { fmtDate, fmtTime, imageUrl, money } from '../lib/format'

// Add an experience on the day it was opened from: only visits the server accepts are listed, each with what it changes and the new total.
export default function AddAttractionDrawer({ pkg, date, onClose, onChanged }) {
  const day = date
  const [opts, setOpts] = useState(null)
  const [reason, setReason] = useState(null)
  const [pick, setPick] = useState(null)
  const [err, setErr] = useState(null)
  const full = dayFull(pkg, day)

  useEffect(() => {
    setOpts(null); setPick(null)
    getChangeOptions(pkg, 'attraction', { date: day }).then(r => { setOpts(r.options); setReason(r.reason) }).catch(e => setErr({ error: e.error }))
  }, [day])

  return <Drawer title={`Add an experience on ${fmtDate(day)}`} onClose={onClose}>
    {err && <div role="alert" className="alert alert-error mb-4 items-start text-sm"><CircleAlert size={18} />
      <div><p className="font-semibold">{err.code === 'CHANGE_REFUSED' ? "That can't be added" : 'Could not add'}</p>
        <ul className="list-disc pl-4">{(err.reasons?.length ? err.reasons : [err.error]).map((r, i) => <li key={i}>{r}</li>)}</ul>
        <p className="mt-1">Your trip is unchanged.</p></div></div>}
    {!opts ? <Spinner label="Finding things to do…" /> : opts.length === 0 ? <p role="status" className="alert alert-info text-sm">{reason || 'No experience fits this day.'}</p> :
      <Paginated key={day} items={opts} size={4} render={o => {
        const sel = pick?.attraction_id === o.attraction_id
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
          <Effects pkg={pkg} preview={o.preview} />
          {sel && <div className="mt-2 flex gap-2"><button className="btn btn-sm flex-1" onClick={() => setPick(null)}>Cancel</button>
            <button className="btn btn-sm btn-primary flex-1" onClick={() => onChanged(o.preview)}>Add to trip</button></div>}
        </article>
      }} />}
  </Drawer>
}
