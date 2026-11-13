import { Fragment } from 'react'
import { ArrowLeft, Car, ChevronLeft, ChevronRight, Clock, ExternalLink, Footprints, Hotel, Pencil, TriangleAlert, Wallet } from 'lucide-react'
import PhotoCarousel from './PhotoCarousel'
import { backLegOf, dayJourney, legOf } from '../lib/legs'
import { Drawer, TYPE_META } from './ui'
import { DAY, KIND_TYPE } from './DayPlan'
import { dayFull, dayView } from '../lib/day'
import { duration, fmtDate, fmtTime, money } from '../lib/format'

const Stat = ({ icon: I, label, value }) => <div className="rounded-xl bg-slate-50 p-3"><p className="flex items-center gap-1 text-xs text-slate-500"><I size={13} />{label}</p><p className="font-bold">{value}</p></div>
// A leg between two stops: how long, how far, and directions in Google Maps.
export const Leg = ({ leg, text }) => <li className="flex items-center gap-3 py-1.5 text-xs text-slate-500">
  <span className="w-20 shrink-0" /><span className="grid w-8 shrink-0 place-items-center"><Car size={14} /></span>
  <span className="flex flex-wrap items-center gap-x-2">{text} · ~{duration(leg.minutes)} · {leg.km} km
    {leg.estimate && <span className="badge badge-ghost badge-xs" title="Estimated from the distance; no live travel time for this leg">estimate</span>}
    <a href={leg.link} target="_blank" rel="noreferrer" className="link link-primary inline-flex items-center gap-0.5">Directions<ExternalLink size={11} /></a></span></li>
const Bookend = ({ text, time }) => <li className="flex items-center gap-3 py-2 text-sm text-slate-600">
  <span className="w-20 shrink-0 font-semibold tabular-nums text-slate-800">{time}</span><span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-amber-100 text-amber-800"><Hotel size={15} /></span>{text}</li>

// Shown in place of the day cards (the map beside it follows the day): back to all days, previous and next day.
function Inline({ title, onClose, onStep, n, count, children }) {
  return <section aria-label={title} className="rounded-2xl border border-slate-200 bg-white p-4">
    <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <button className="btn btn-sm btn-ghost" onClick={onClose}><ArrowLeft size={15} />All days</button>
      <h2 className="text-lg font-bold">{title}</h2>
      <span className="flex gap-1">
        <button className="btn btn-sm btn-outline" disabled={n === 0} onClick={() => onStep(-1)} aria-label="Previous day"><ChevronLeft size={15} /></button>
        <button className="btn btn-sm btn-outline" disabled={n === count - 1} onClick={() => onStep(1)} aria-label="Next day"><ChevronRight size={15} /></button>
      </span>
    </header>
    {children}
  </section>
}

// One day: photos of every place, the timeline from the hotel and back with travel legs and durations, and the
// day's totals. A side drawer by default; `inline` (with onStep) shows it in the page instead.
export default function DayDetail({ pkg, day, n, onClose, onOpen, onChange, onAdd, inline, onStep }) {
  const v = dayView(pkg, day)
  const visits = v.events.some(e => e.kind === 'ATTRACTION')
  // leave the hotel -> each visit -> back at the hotel, with times from the travel legs (older packages: no legs)
  const visitIdx = v.events.flatMap((e, i) => e.kind === 'ATTRACTION' && e.item ? [i] : [])
  const trip = dayJourney(visitIdx.map(i => v.events[i].item))
  const firstVisit = visitIdx[0], lastVisit = visitIdx[visitIdx.length - 1]
  const Shell = inline ? Inline : Drawer
  return <Shell wide title={`Day ${n + 1} · ${fmtDate(day.date)}`} onClose={onClose} onStep={onStep} n={n} count={pkg.days.length}>
    <p className="mb-3 text-slate-600">{DAY[day.day_type]}{day.city && ` in ${day.city}`}</p>
    <PhotoCarousel photos={v.photos} className="h-60 rounded-xl" />
    <div className="my-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
      <Stat icon={Footprints} label="Visiting" value={duration(v.visitMinutes)} />
      <Stat icon={Clock} label="Travel" value={duration(v.travelMinutes)} />
      <Stat icon={Clock} label="First to last" value={duration(v.spanMinutes)} />
      <Stat icon={Wallet} label="Tickets & travel" value={money(v.cost)} />
    </div>
    <ol className="divide-y divide-slate-100" aria-label="Timeline">
      {visits && !trip && v.startAt && <Bookend text={`Start from ${v.startAt.name}`} />}
      {v.events.map((e, i) => {
        const M = TYPE_META[KIND_TYPE[e.kind]], it = e.item
        const until = it && e.minutes != null && it.end ? fmtTime(it.end) : null
        const leg = e.kind === 'ATTRACTION' && it && legOf(it), back = e.kind === 'ATTRACTION' && it && backLegOf(it)
        return <Fragment key={i}>
        {trip && i === firstVisit && <Bookend time={trip.leave.time} text={`Leave ${trip.leave.place}`} />}
        {leg && <Leg leg={leg} text={`${leg.from} → ${it.name}`} />}
        <li className="flex items-start gap-3 py-2">
          <span className="w-20 shrink-0 pt-1 text-sm font-semibold tabular-nums">{e.time}{until && <span className="block text-xs font-normal text-slate-500">to {until}</span>}</span>
          <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${M.color}`}><M.icon size={15} /></span>
          <div className="min-w-0 flex-1">
            <p className="font-medium">{e.title}</p>
            <p className="text-xs text-slate-500">{[e.minutes != null && duration(e.minutes), it?.type === 'hotel' && it.details?.rating && `${it.details.rating} guest rating`, it?.price_inr > 0 && e.minutes != null && money(it.price_inr)].filter(Boolean).join(' · ')}</p>
            {e.kind === 'ATTRACTION' && it?.warnings?.map((w, j) => <p key={j} className="mt-1 flex items-center gap-1 text-xs text-amber-700"><TriangleAlert size={12} />{typeof w === 'string' ? w : w.message}</p>)}
          </div>
          {it && <div className="flex shrink-0 gap-1">
            {onChange && it.type !== 'transfer' && <button className="btn btn-xs btn-outline" onClick={() => onChange(it)}><Pencil size={12} />{it.type === 'attraction' ? 'Remove' : 'Change'}</button>}
            <button className="btn btn-xs btn-ghost" onClick={() => onOpen(it)}>Details</button>
          </div>}
        </li>
        {back && <Leg leg={back} text={`${it.name} → ${back.to}`} />}
        {trip?.back && i === lastVisit && <Bookend time={trip.back.time} text={`Back at ${trip.back.place}`} />}
        </Fragment>
      })}
      {visits && !trip && v.endAt && <Bookend text={`Back to ${v.endAt.name}`} />}
    </ol>
    {onAdd && <span className="mt-4 inline-block" title={dayFull(pkg, day.date) ? 'Remove 1 to add another' : undefined}>
      <button className="btn btn-outline btn-sm" disabled={dayFull(pkg, day.date)} onClick={() => onAdd(day.date)}>+ Add an experience this day</button></span>}
  </Shell>
}
