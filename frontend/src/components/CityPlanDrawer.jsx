import { useEffect, useState } from 'react'
import { CircleAlert, TriangleAlert } from 'lucide-react'
import { Drawer, Paginated, Spinner } from './ui'
import { Diff } from './ChangeDrawer'
import { change, getCityPlans } from '../lib/api'
import { money } from '../lib/format'

export const planText = plan => plan.map(s => `${s.city} · ${s.nights}n`).join(' → ')

// G3: choose another route and split of the nights. The server builds the whole package again for it.
export default function CityPlanDrawer({ pkg, onClose, onChanged }) {
  const [opts, setOpts] = useState(null)
  const [pick, setPick] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  useEffect(() => { getCityPlans(pkg).then(r => setOpts(r.options)).catch(e => setErr({ error: e.error })) }, [])

  async function apply(o) {
    setBusy(true); setErr(null)
    try { onChanged(await change(pkg, { action: 'change_city_plan', plan: o.plan })) }
    catch (e) { setErr(e); setPick(null) } finally { setBusy(false) }
  }

  return <Drawer title="Change cities" onClose={onClose}>
    <p className="mb-4 text-sm text-slate-600">Now: <b>{planText(pkg.cities.map(c => ({ city: c.city, nights: c.nights })))}</b>. Prices show the difference to your trip total.</p>
    {err && <div role="alert" className="alert alert-error mb-4 items-start text-sm"><CircleAlert size={18} />
      <div><p className="font-semibold">{err.code === 'CHANGE_REFUSED' ? "That plan isn't possible" : 'Could not change'}</p>
        <ul className="list-disc pl-4">{(err.reasons?.length ? err.reasons : [err.error]).map((r, i) => <li key={i}>{r}</li>)}</ul>
        <p className="mt-1">Your trip is unchanged.</p></div></div>}
    {!opts && !err ? <Spinner label="Finding other routes…" /> : opts && <Paginated items={opts} size={5} render={o => {
      const sel = pick === o
      return <article key={planText(o.plan)} className={`rounded-xl border p-3 ${o.is_current ? 'border-primary bg-brand-soft' : 'border-slate-200'}`}>
        <h3 className="font-semibold leading-tight">{planText(o.plan)}</h3>
        <div className="mt-2 flex items-center justify-between"><span><b>{money(o.total_inr)}</b> <Diff v={o.price_diff_inr} /></span>
          {o.is_current ? <span className="badge badge-primary">Current</span> : <button className="btn btn-sm btn-outline" onClick={() => { setPick(o); setErr(null) }}>Select</button>}</div>
        {!o.fits_budget && !o.is_current && <p className="mt-1 text-xs text-amber-700">Over your {money(pkg.budget_inr)} budget</p>}
        {sel && <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
          <p>New trip total <b>{money(o.total_inr)}</b> <span className="text-slate-500">(was {money(pkg.total_inr)})</span></p>
          {!o.fits_budget && <p className="mt-1 flex items-center gap-1 text-amber-700"><TriangleAlert size={14} />This goes {money(o.total_inr - pkg.budget_inr)} over your budget.</p>}
          <p className="mt-1 text-slate-600">Flights, stays, transfers and experiences are chosen again for the new cities.</p>
          <div className="mt-2 flex gap-2"><button className="btn btn-sm flex-1" onClick={() => setPick(null)}>Cancel</button>
            <button className="btn btn-sm btn-primary flex-1" disabled={busy} onClick={() => apply(o)}>{busy ? 'Updating…' : 'Confirm change'}</button></div>
        </div>}
      </article>
    }} />}
  </Drawer>
}
