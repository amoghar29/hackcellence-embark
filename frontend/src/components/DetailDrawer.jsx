import { useEffect, useState } from 'react'
import { Check, X } from 'lucide-react'
import { Drawer, Img, Spinner, TypeBadge } from './ui'
import { API, getDetail } from '../lib/api'
import { duration, fmtDate, fmtTime, imageUrl, money } from '../lib/format'

const yn = v => v ? <Check size={16} className="text-emerald-600" aria-label="Yes" /> : <X size={16} className="text-slate-400" aria-label="No" />
const Rows = ({ rows }) => <dl className="divide-y divide-slate-100 text-sm">{rows.filter(r => r[1] != null && r[1] !== '').map(([k, v]) =>
  <div key={k} className="flex justify-between gap-4 py-2"><dt className="text-slate-500">{k}</dt><dd className="text-right font-medium">{v}</dd></div>)}</dl>

function Body({ item, d }) {
  const photo = imageUrl(d.image, API)
  if (item.type === 'hotel') return <>
    <Img src={photo} alt={d.name} className="mb-4 h-56 w-full rounded-xl" />
    <p className="mb-2 text-slate-600">{d.area}, {d.city} · {'★'.repeat(d.stars)} · {d.rating} guest rating</p>
    <Rows rows={[['Check-in from', d.check_in_from], ['Check-out until', d.check_out_until], ['Family friendly', yn(d.family_friendly)], ['Your stay', `${fmtDate(item.start)} → ${fmtDate(item.end)}`]]} />
    <h3 className="mb-2 mt-5 font-bold">Room types</h3>
    <ul className="space-y-2">{d.rooms.map(r => <li key={r.room_id} className={`rounded-xl border p-3 text-sm ${r.room_id === item.room_id ? 'border-primary bg-brand-soft' : 'border-slate-200'}`}>
      <div className="flex justify-between font-semibold"><span>{r.name}{r.room_id === item.room_id && ' · your room'}</span><span>{money(r.price_per_night_inr)}/night</span></div>
      <p className="text-slate-500">Up to {r.max_adults} adults, {r.max_children} children · {r.refundable ? 'Refundable' : 'Non-refundable'}</p></li>)}</ul>
  </>
  if (item.type === 'flight') return <Rows rows={[
    ['Flight', `${d.airline} ${d.flight_number}`], ['From', `${d.from_airport_name} (${d.from_airport})`], ['Departs', `${fmtDate(d.departure_local)}, ${fmtTime(d.departure_local)}`],
    ['To', `${d.to_airport_name} (${d.to_airport})`], ['Arrives', `${fmtDate(d.arrival_local)}, ${fmtTime(d.arrival_local)}`], ['Duration', duration(d.duration_minutes)],
    ['Stops', d.stops ? d.stops : 'Non-stop'], ['Cabin', d.cabin], ['Price per seat', money(d.price_per_seat_inr)], ['Seats booked', item.quantity], ['Local times', 'All times are local to each airport']]} />
  if (item.type === 'transfer') return <Rows rows={[
    ['Service', d.name], ['Type', d.type?.replaceAll('_', ' ').toLowerCase()], ['From', d.from_point], ['To', d.to_point], ['Door to door', yn(d.door_to_door)],
    ['Duration', duration(d.duration_minutes)], ['Runs', d.service_from && `${d.service_from} – ${d.service_until}`], ['Every', d.frequency_minutes && `${d.frequency_minutes} min`],
    ['Fits', d.max_passengers && `${d.max_passengers} passengers`], [d.pricing === 'PER_VEHICLE' ? 'Price per vehicle' : 'Price per person', d.price_inr != null && money(d.price_inr)], ['You pay', `${money(item.price_inr)} for ${item.quantity} ${d.pricing === 'PER_VEHICLE' ? 'vehicle' : 'ticket'}${item.quantity > 1 ? 's' : ''}`], ['Child price', d.child_price_inr != null && money(d.child_price_inr)]]} />
  return <>
    <Img src={photo} alt={d.name} className="mb-4 h-56 w-full rounded-xl" />
    {d.name_ja && <p className="mb-2 text-slate-500">{d.name_ja}</p>}
    <Rows rows={[['Category', d.category], ['Visit time', `${d.visit_minutes} min`], ['Open', `${d.open_from} – ${d.open_until}`], ['Open days', d.open_days?.join?.(', ') ?? d.open_days],
      ['Child friendly', yn(d.child_friendly)], ['Accessible', yn(d.accessible)], ['Adult ticket', money(d.price_per_person_inr)],
      ['Child ticket', d.child_price_inr == null ? 'Adult price' : d.child_price_inr === 0 ? 'Free' : money(d.child_price_inr)], ['Planned visit', `${fmtDate(item.start)}, ${fmtTime(item.start)}–${fmtTime(item.end)}`], ['You pay', `${money(item.price_inr)} for ${item.quantity} ${item.quantity > 1 ? 'people' : 'person'}`]]} />
  </>
}

export default function DetailDrawer({ item, onClose }) {
  const [d, setD] = useState(null), [err, setErr] = useState('')
  useEffect(() => { getDetail(item.type, item.catalog_id).then(setD).catch(e => setErr(e.error)) }, [item])
  return <Drawer title={item.name} onClose={onClose}>
    <div className="mb-3"><TypeBadge type={item.type} /></div>
    {err ? <p role="alert" className="text-red-600">{err}</p> : !d ? <Spinner /> : <Body item={item} d={d} />}
  </Drawer>
}
