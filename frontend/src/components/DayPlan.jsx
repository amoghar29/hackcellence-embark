import { Clock, Footprints } from 'lucide-react'
import { Img, TYPE_META } from './ui'
import { API } from '../lib/api'
import { dayView } from '../lib/day'
import { duration, fmtDate, imageUrl } from '../lib/format'

export const DAY = { TRAVEL: 'Travel day', ARRIVAL: 'Arrival', FULL: 'Full day', CITY_CHANGE: 'Moving on', RETURN: 'Heading home', HOME: 'Back home' }
export const KIND_TYPE = { FLIGHT_DEPARTURE: 'flight', FLIGHT_ARRIVAL: 'flight', TRANSFER: 'transfer', CHECK_IN: 'hotel', CHECK_OUT: 'hotel', ATTRACTION: 'attraction' }

// Every day as a compact card, side by side, so the whole trip fits on one screen. A card opens the day popup.
export default function DayPlan({ pkg, onDay }) {
  return <ol className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Days">{pkg.days.map((d, n) => {
    const v = dayView(pkg, d)
    return <li key={d.date}><button onClick={() => onDay(d)} className="flex h-full w-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white text-left transition hover:border-brand hover:shadow-md"
      aria-label={`Day ${n + 1}, ${fmtDate(d.date)}: open the day plan`}>
      <div className="flex h-16 w-full gap-px bg-slate-100">{v.photos.slice(0, 3).map(p => <Img key={p.path} src={imageUrl(p.path, API)} className="h-full flex-1" />)}</div>
      <div className="flex flex-1 flex-col gap-2 p-3">
        <header className="flex items-baseline justify-between gap-2">
          <h3 className="font-bold">Day {n + 1} <span className="font-normal text-slate-500">· {fmtDate(d.date)}</span></h3>
          <span className="truncate text-xs text-slate-500">{DAY[d.day_type]}{d.city && ` · ${d.city}`}</span>
        </header>
        <ol className="space-y-1">{v.events.slice(0, 4).map((e, i) => {
          const M = TYPE_META[KIND_TYPE[e.kind]]
          return <li key={i} className="flex items-center gap-2 text-xs">
            <span className="w-10 shrink-0 font-semibold tabular-nums">{e.time}</span>
            <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full ${M.color}`}><M.icon size={11} /></span>
            <span className="truncate">{e.title}</span>
          </li>
        })}{v.events.length > 4 && <li className="pl-12 text-xs text-slate-500">+{v.events.length - 4} more</li>}</ol>
        <p className="mt-auto flex gap-3 pt-1 text-xs text-slate-600">
          {v.visitMinutes > 0 && <span className="flex items-center gap-1"><Footprints size={12} />{duration(v.visitMinutes)} visiting</span>}
          {v.travelMinutes > 0 && <span className="flex items-center gap-1"><Clock size={12} />{duration(v.travelMinutes)} travel</span>}
        </p>
      </div>
    </button></li>
  })}</ol>
}
