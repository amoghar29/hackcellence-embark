import { useEffect, useState } from 'react'
import { CalendarDays, ChevronRight, MapPin, Users } from 'lucide-react'
import { Spinner } from '../components/ui'
import { getReservations } from '../lib/api'
import { fmtDate, money } from '../lib/format'
import { reservationHash } from '../lib/route'

// Every booked package, newest first. Each card opens its reservation summary.
export default function BookingsPage() {
  const [list, setList] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    getReservations().then(r => setList(r.reservations.filter(p => p.reference)))
      .catch(e => setErr(e.error || 'We could not load your bookings.'))
  }, [])

  if (err) return <div className="mx-auto max-w-xl p-8 text-center"><p role="alert" className="mb-4 text-lg">{err}</p><a className="btn btn-primary" href="#/">Plan a new trip</a></div>
  if (!list) return <Spinner label="Loading your bookings…" />

  return <main className="mx-auto max-w-3xl px-4 pb-16 pt-8">
    <h1 className="text-2xl font-bold">My bookings</h1>
    {list.length === 0
      ? <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="text-lg">You have no bookings yet.</p>
          <a className="btn btn-primary mt-4" href="#/">Plan a trip</a>
        </div>
      : <ul className="mt-6 grid gap-4" aria-label="Booked trips">{list.map(p => <li key={p.reference} className="relative">
          <a href={reservationHash(p.reference)} className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5 transition hover:border-brand hover:shadow-md">
            <div className="flex-1 space-y-1">
              <p className="text-lg font-bold">{p.country}</p>
              <p className="flex flex-wrap gap-x-4 text-sm text-slate-600">
                <span className="flex items-center gap-1"><CalendarDays size={14} />{fmtDate(p.start_date)} → {fmtDate(p.end_date)} · {p.nights} nights</span>
                <span className="flex items-center gap-1"><Users size={14} />{p.traveler.adults} adult{p.traveler.adults > 1 ? 's' : ''}{p.traveler.children > 0 && `, ${p.traveler.children} child${p.traveler.children > 1 ? 'ren' : ''}`}</span>
              </p>
              <p className="flex items-center gap-1 text-sm text-slate-600"><MapPin size={14} />{p.cities.map(c => c.city).join(' → ')}</p>
            </div>
            <div className="self-start text-right">
              <p className="font-bold">{money(p.total_inr)}</p>
              <p className="text-xs text-slate-500">No. <span className="font-mono tracking-wider">{p.reference}</span></p>
            </div>
            <ChevronRight size={20} className="shrink-0 text-slate-400" aria-hidden />
          </a>
        </li>)}</ul>}
  </main>
}
