import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, CalendarDays, CircleAlert, Copy, Download, PartyPopper, TriangleAlert, Users, X } from 'lucide-react'
import PhotoCarousel from '../components/PhotoCarousel'
import PhotoStrips from '../components/PhotoStrips'
import DayDetail from '../components/DayDetail'
import ItemCard from '../components/ItemCard'
import DetailDrawer from '../components/DetailDrawer'
import ChangeDrawer from '../components/ChangeDrawer'
import AddAttractionDrawer from '../components/AddAttractionDrawer'
import DayPlan from '../components/DayPlan'
import MapView from '../components/MapView'
import { Modal, Paginated, Spinner, TYPE_META } from '../components/ui'
import { book, getReservation } from '../lib/api'
import { bookingKey } from '../lib/idempotency'
import { loadPackage, savePackage } from '../lib/results'
import { fmtDate, money } from '../lib/format'
import { carouselPhotos, changeSummary, itemsOf, priceBreakdown, TYPES, tripExport } from '../lib/trip'
import { reservationHash, resultsHash } from '../lib/route'
import { attractionsByDay } from '../lib/legs'
import { dayFull } from '../lib/day'

const TABS = [['days', 'Day by day'], ...TYPES.map(t => [t, t === 'attraction' ? 'Attractions covered' : TYPE_META[t].plural])]

// `id` is the package's position in the search results (a package has no id until it is booked);
// `reference` opens a reservation.
export default function PackagePage({ id, reference }) {
  const [pkg, setPkg] = useState(null)
  const [loadErr, setLoadErr] = useState('')
  const [tab, setTab] = useState('days')
  const [detail, setDetail] = useState(null)
  const [changing, setChanging] = useState(null)
  const [adding, setAdding] = useState(null)
  const [dayOpen, setDayOpen] = useState(null) // date of the day popup; looked up again after every change
  const [summary, setSummary] = useState(null)
  const [confirm, setConfirm] = useState(false)
  const [booking, setBooking] = useState(false)
  const [bookErr, setBookErr] = useState('')
  const key = useRef(bookingKey())

  useEffect(() => {
    setPkg(null); setLoadErr('')
    if (!reference) {
      const found = loadPackage(Number(id))
      if (found) setPkg(found); else setLoadErr('We could not find this trip. Search again to see your packages.')
      return
    }
    getReservation(reference).then(setPkg)
      .catch(e => setLoadErr(e.code === 'NOT_FOUND' ? 'Reservation not found.' : e.error))
  }, [id, reference])

  const exportJson = () => {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([JSON.stringify(tripExport(pkg), null, 2)], { type: 'application/json' }))
    a.download = `holiday-package${pkg.reference ? `-${pkg.reference}` : ''}.json`
    a.click(); URL.revokeObjectURL(a.href)
  }
  if (loadErr) return <div className="mx-auto max-w-xl p-8 text-center"><p role="alert" className="mb-4 text-lg">{loadErr}</p><a className="btn btn-primary" href="#/">Plan a new trip</a></div>
  if (!pkg) return <Spinner label="Opening your trip…" />

  const planned = pkg.status === 'PLANNED' && !reference
  const canEdit = planned
  const over = pkg.remaining_inr < 0
  const parts = priceBreakdown(pkg.items)
  const usedPct = Math.min(100, Math.round(pkg.total_inr / pkg.budget_inr * 100))

  // `next` is the changed package plus `notices` (G1): what the server fixed or the traveler should know.
  function changed({ notices = [], ...next }) {
    setSummary({ ...changeSummary(pkg, next), notices, ids: next.items.filter(n => !pkg.items.some(o => o.item_id === n.item_id && o.catalog_id === n.catalog_id)).map(n => n.item_id) })
    savePackage(Number(id), next)
    setPkg(next); setChanging(null); setAdding(null)
  }

  async function doBook() {
    setBooking(true); setBookErr('')
    // the key follows the selection: a changed package is a different booking and must not reuse an old key
    try { const r = await book(pkg, key.current.get(JSON.stringify(pkg.selection))); key.current.clear(); window.location.hash = reservationHash(r.reference) }
    catch (e) {
      if (e.code === 'IDEMPOTENCY_KEY_REUSED') key.current.clear()
      setBookErr(e.code === 'SOLD_OUT' ? `${e.part === 'flight' ? 'A flight' : 'A hotel room'} was just taken by someone else. Nothing was booked or charged. Change that part of your trip, or search again.` : e.error)
    } finally { setBooking(false); setConfirm(false) }
  }

  return <main className="mx-auto max-w-6xl px-4 pb-32 pt-6">
    <a href={resultsHash} className="mb-4 inline-flex items-center gap-1 text-sm text-slate-600 hover:underline"><ArrowLeft size={15} />Back to results</a>

    {pkg.status === 'BOOKED' && <div className="mb-5 flex items-center gap-4 rounded-2xl bg-emerald-50 p-5 text-emerald-900">
      <PartyPopper size={28} className="shrink-0" />
      <div className="flex-1"><p className="font-bold">You're booked for {pkg.country}!</p>
        <p className="text-sm">Reservation number <b className="select-all text-lg tracking-wider">{reference}</b></p></div>
      <button className="btn btn-sm btn-ghost" onClick={() => navigator.clipboard?.writeText(reference)} aria-label="Copy reservation number"><Copy size={16} /></button>
    </div>}
    {bookErr && <div role="alert" className="alert alert-error mb-5"><CircleAlert size={18} /><span>{bookErr}</span></div>}

    <section className="grid overflow-hidden rounded-2xl border border-slate-200 bg-white lg:grid-cols-[1.1fr_1fr]" aria-label="Package summary">
      <PhotoCarousel photos={carouselPhotos(pkg)} className="h-72 lg:h-full lg:min-h-[26rem]" />
      <div className="flex flex-col gap-4 p-6">
        <div>
          <h1 className="text-2xl font-bold">{pkg.country} · {pkg.nights} nights</h1>
          <p className="mt-1 flex flex-wrap gap-x-4 text-slate-600">
            <span className="flex items-center gap-1"><CalendarDays size={15} />{fmtDate(pkg.start_date)} → {fmtDate(pkg.end_date)}</span>
            <span className="flex items-center gap-1"><Users size={15} />{pkg.traveler.adults} adult{pkg.traveler.adults > 1 ? 's' : ''}{pkg.traveler.children > 0 && `, ${pkg.traveler.children} child${pkg.traveler.children > 1 ? 'ren' : ''}`}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ol className="flex flex-wrap items-center gap-2" aria-label="Cities">{pkg.cities.map((c, i) =>
            <li key={c.city} className="flex items-center gap-2"><span className="rounded-full bg-brand-soft px-3 py-1 text-sm font-semibold">{c.city} · {c.nights}n</span>{i < pkg.cities.length - 1 && <span aria-hidden>→</span>}</li>)}</ol>
        </div>
        <dl className="divide-y divide-slate-100 text-sm">{TYPES.map(t => parts[t] > 0 && <div key={t} className="flex justify-between py-2">
          <dt className="flex items-center gap-2">{(() => { const M = TYPE_META[t]; return <M.icon size={15} /> })()}{TYPE_META[t].plural} <span className="text-slate-400">({itemsOf(pkg, t).length})</span></dt><dd className="font-medium">{money(parts[t])}</dd></div>)}</dl>
        <div>
          <div className="flex items-baseline justify-between"><span className="font-semibold">Trip total</span><b className="text-2xl">{money(pkg.total_inr)}</b></div>
          <progress className={`progress mt-2 w-full ${over ? 'progress-error' : 'progress-primary'}`} value={usedPct} max="100" aria-label="Budget used" />
          <p className={`mt-1 text-sm ${over ? 'text-red-600' : 'text-slate-600'}`}>{over ? `${money(-pkg.remaining_inr)} over` : `${money(pkg.remaining_inr)} left of`} your {money(pkg.budget_inr)} budget</p>
        </div>
        <button className="btn btn-sm btn-outline" onClick={exportJson}><Download size={14} />Export JSON</button>
        {planned && <button className="btn btn-primary btn-lg mt-auto" onClick={() => setConfirm(true)}>Book this trip · {money(pkg.total_inr)}</button>}
      </div>
    </section>
    <PhotoStrips pkg={pkg} onOpen={setDetail} />

    {summary && <div role="status" className="alert alert-success mt-5 items-start">
      <div className="flex-1"><p className="font-bold">Trip updated</p>
        <ul className="text-sm">{summary.changed.map((c, i) => <li key={i}>{TYPE_META[c.type].label}: {c.from && <s className="opacity-70">{c.from}</s>} {c.from && c.to && '→'} {c.to ?? 'removed'}</li>)}</ul>
        <p className="text-sm">Total {money(summary.totalBefore)} → <b>{money(summary.totalAfter)}</b> ({summary.delta <= 0 ? 'saves ' : '+'}{money(Math.abs(summary.delta))})</p>
        {summary.notices.length > 0 && <ul className="mt-2 space-y-1 rounded-lg bg-white/60 p-2 text-sm" aria-label="Also changed">{summary.notices.map((n, i) =>
          <li key={i} className="flex gap-2"><TriangleAlert size={15} className="mt-0.5 shrink-0" /><span>{n.message}</span></li>)}</ul>}</div>
      <button className="btn btn-sm btn-circle btn-ghost" onClick={() => setSummary(null)} aria-label="Dismiss"><X size={16} /></button>
    </div>}

    <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]"><div className="min-w-0">
    <div role="tablist" className="tabs tabs-border mb-6 overflow-x-auto whitespace-nowrap">{TABS.map(([k, label]) =>
      <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? 'tab-active font-semibold' : ''}`} onClick={() => setTab(k)}>{label}{TYPES.includes(k) && ` (${itemsOf(pkg, k).length})`}</button>)}</div>

    {tab === 'attraction' && (() => { const days = attractionsByDay(pkg); return days.length === 0 ? <p className="text-slate-600">No attractions in this trip yet.</p> : <>
      <p className="mb-4 text-slate-600">{itemsOf(pkg, 'attraction').length} attractions in {new Set(days.map(d => d.city)).size} {new Set(days.map(d => d.city)).size === 1 ? 'city' : 'cities'}, over {days.length} days.</p>
      <Paginated items={days} size={3} render={d => <section key={d.date} className="mb-5">
        <div className="mb-2 flex items-center justify-between gap-2"><h3 className="font-bold">{fmtDate(d.date)} · {d.city}</h3>
          {canEdit && <span title={dayFull(pkg, d.date) ? 'Remove 1 to add another' : undefined}>
            <button className="btn btn-outline btn-sm" disabled={dayFull(pkg, d.date)} onClick={() => setAdding(d.date)}>+ Add this day</button></span>}</div>
        <div className="grid gap-3">{d.items.map(it => <ItemCard key={it.item_id} item={it} onOpen={setDetail} onChange={setChanging} canChange={canEdit} updated={summary?.ids.includes(it.item_id)} />)}</div>
      </section>} /></> })()}
    {TYPES.includes(tab) && tab !== 'attraction' && (() => { const list = itemsOf(pkg, tab); return list.length === 0 ? <p className="text-slate-600">None in this trip.</p> :
      <Paginated key={tab} items={list} size={5} render={it => <ItemCard key={it.item_id} item={it} onOpen={setDetail} onChange={setChanging} canChange={canEdit} updated={summary?.ids.includes(it.item_id)} />} /> })()}
    {tab === 'days' && (() => {
      const n = pkg.days.findIndex(d => d.date === dayOpen)
      if (n < 0) return <DayPlan pkg={pkg} onDay={d => setDayOpen(d.date)} />
      return <DayDetail inline pkg={pkg} day={pkg.days[n]} n={n} onClose={() => setDayOpen(null)} onStep={s => setDayOpen(pkg.days[n + s].date)}
        onOpen={setDetail} onChange={canEdit ? setChanging : undefined} onAdd={canEdit && dayOpen >= pkg.start_date && dayOpen <= pkg.end_date ? setAdding : undefined} />
    })()}
    </div>
    <aside className="lg:sticky lg:top-20 lg:self-start" aria-label="Map">
      <MapView pkg={pkg} onOpen={setDetail} day={tab === 'days' ? dayOpen || '' : ''} onDay={d => { setTab('days'); setDayOpen(d || null) }} /></aside></div>


    {detail && <DetailDrawer item={detail} onClose={() => setDetail(null)} />}
    {adding && <AddAttractionDrawer pkg={pkg} date={adding} onClose={() => setAdding(null)} onChanged={changed} />}
    {changing && <ChangeDrawer pkg={pkg} item={changing} onClose={() => setChanging(null)} onChanged={changed} />}
    {confirm && <Modal label="Confirm booking" onClose={() => setConfirm(false)}>
      <div className="p-6"><h2 className="text-xl font-bold">Book this trip?</h2>
        <p className="mt-2 text-slate-600">{pkg.country}, {fmtDate(pkg.start_date)} → {fmtDate(pkg.end_date)} for <b>{money(pkg.total_inr)}</b>. Seats and rooms are reserved straight away.</p>
        {over && <p className="mt-2 text-amber-700">This is {money(-pkg.remaining_inr)} over your budget.</p>}
        <div className="mt-5 flex gap-2"><button className="btn flex-1" onClick={() => setConfirm(false)}>Not yet</button>
          <button className="btn btn-primary flex-1" disabled={booking} onClick={doBook}>{booking ? 'Booking…' : 'Confirm booking'}</button></div></div>
    </Modal>}
  </main>
}
