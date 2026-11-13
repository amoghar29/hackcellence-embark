import { Paginated, TYPE_META } from './ui'
import { fmtDate } from '../lib/format'

const DAY = { TRAVEL: 'Travel day', ARRIVAL: 'Arrival', FULL: 'Full day', CITY_CHANGE: 'Moving on', RETURN: 'Heading home', HOME: 'Back home' }
const KIND_TYPE = { FLIGHT_DEPARTURE: 'flight', FLIGHT_ARRIVAL: 'flight', TRANSFER: 'transfer', CHECK_IN: 'hotel', CHECK_OUT: 'hotel', ATTRACTION: 'attraction' }

export default function DayPlan({ pkg, onOpen, onAdd }) {
  const byId = Object.fromEntries(pkg.items.map(i => [i.item_id, i]))
  return <Paginated items={pkg.days} size={3} render={(d, n) =>
    <section key={d.date} className="rounded-2xl border border-slate-200 bg-white p-4">
      <header className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-lg font-bold">{fmtDate(d.date)}</h3>
        <span className="text-sm text-slate-500">{DAY[d.day_type]}{d.city && ` · ${d.city}`}</span>
      </header>
      <ol className="space-y-2">{d.events.map((e, i) => {
        const M = TYPE_META[KIND_TYPE[e.kind]], item = byId[e.item_id]
        return <li key={i}><button onClick={() => item && onOpen(item)} className="flex w-full items-center gap-3 rounded-xl p-2 text-left hover:bg-slate-50">
          <span className="w-12 shrink-0 text-sm font-semibold tabular-nums">{e.time}</span>
          <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${M.color}`}><M.icon size={15} /></span>
          <span className="text-sm">{e.title}</span>
        </button></li>
      })}</ol>
      {onAdd && d.date >= pkg.start_date && d.date <= pkg.end_date && <button className="btn btn-sm btn-ghost mt-2" onClick={() => onAdd(d.date)}>+ Add an experience</button>}
    </section>} />
}
