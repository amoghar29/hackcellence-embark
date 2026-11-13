import { Clock, Footprints, Hotel, Pencil, Wallet } from 'lucide-react'
import PhotoCarousel from './PhotoCarousel'
import { Drawer, TYPE_META } from './ui'
import { DAY, KIND_TYPE } from './DayPlan'
import { dayView } from '../lib/day'
import { duration, fmtDate, fmtTime, money } from '../lib/format'

const Stat = ({ icon: I, label, value }) => <div className="rounded-xl bg-slate-50 p-3"><p className="flex items-center gap-1 text-xs text-slate-500"><I size={13} />{label}</p><p className="font-bold">{value}</p></div>
const Bookend = ({ text }) => <li className="flex items-center gap-3 py-2 text-sm text-slate-600">
  <span className="w-20 shrink-0" /><span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-amber-100 text-amber-800"><Hotel size={15} /></span>{text}</li>

// The day popup: photos of every place, the timeline from the hotel and back with durations, and the day's totals.
export default function DayDetail({ pkg, day, n, onClose, onOpen, onChange, onAdd }) {
  const v = dayView(pkg, day)
  const visits = v.events.some(e => e.kind === 'ATTRACTION')
  return <Drawer wide title={`Day ${n + 1} · ${fmtDate(day.date)}`} onClose={onClose}>
    <p className="mb-3 text-slate-600">{DAY[day.day_type]}{day.city && ` in ${day.city}`}</p>
    <PhotoCarousel photos={v.photos} className="h-60 rounded-xl" />
    <div className="my-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
      <Stat icon={Footprints} label="Visiting" value={duration(v.visitMinutes)} />
      <Stat icon={Clock} label="Travel" value={duration(v.travelMinutes)} />
      <Stat icon={Clock} label="First to last" value={duration(v.spanMinutes)} />
      <Stat icon={Wallet} label="Tickets & travel" value={money(v.cost)} />
    </div>
    <ol className="divide-y divide-slate-100" aria-label="Timeline">
      {visits && v.startAt && <Bookend text={`Start from ${v.startAt.name}`} />}
      {v.events.map((e, i) => {
        const M = TYPE_META[KIND_TYPE[e.kind]], it = e.item
        const until = it && e.minutes != null && it.end ? fmtTime(it.end) : null
        return <li key={i} className="flex items-start gap-3 py-2">
          <span className="w-20 shrink-0 pt-1 text-sm font-semibold tabular-nums">{e.time}{until && <span className="block text-xs font-normal text-slate-500">to {until}</span>}</span>
          <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${M.color}`}><M.icon size={15} /></span>
          <div className="min-w-0 flex-1">
            <p className="font-medium">{e.title}</p>
            <p className="text-xs text-slate-500">{[e.minutes != null && duration(e.minutes), it?.type === 'hotel' && it.details?.rating && `${it.details.rating} guest rating`, it?.price_inr > 0 && e.minutes != null && money(it.price_inr)].filter(Boolean).join(' · ')}</p>
          </div>
          {it && <div className="flex shrink-0 gap-1">
            {onChange && it.type !== 'transfer' && <button className="btn btn-xs btn-outline" onClick={() => onChange(it)}><Pencil size={12} />{it.type === 'attraction' ? 'Remove' : 'Change'}</button>}
            <button className="btn btn-xs btn-ghost" onClick={() => onOpen(it)}>Details</button>
          </div>}
        </li>
      })}
      {visits && v.endAt && <Bookend text={`Back to ${v.endAt.name}`} />}
    </ol>
    {onAdd && <button className="btn btn-outline btn-sm mt-4" onClick={() => onAdd(day.date)}>+ Add an experience this day</button>}
  </Drawer>
}
