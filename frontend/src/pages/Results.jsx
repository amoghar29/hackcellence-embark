import { useState } from 'react'
import { ArrowLeft, CalendarDays, Users } from 'lucide-react'
import PhotoCarousel from '../components/PhotoCarousel'
import { Paginated } from '../components/ui'
import { loadResults, SORTS } from '../lib/results'
import { carouselPhotos, itemsOf } from '../lib/trip'
import { fmtDate, money } from '../lib/format'
import { packageHash } from '../lib/route'

const PAGE_SIZE = 10

function PackageCard({ pkg }) {
  const over = pkg.remaining_inr < 0
  const t = pkg.traveler
  return <article className="grid overflow-hidden rounded-2xl border border-slate-200 bg-white md:grid-cols-[1fr_1.2fr]">
    <PhotoCarousel photos={carouselPhotos(pkg).slice(0, 8)} className="h-56 md:h-full md:min-h-60" />
    <div className="flex flex-col gap-3 p-5">
      <div>
        <h2 className="text-xl font-bold">{pkg.cities.map(c => c.city).join(' → ')}</h2>
        <p className="text-sm text-slate-600">{pkg.country} · {pkg.nights} nights</p>
      </div>
      <p className="flex flex-wrap gap-x-4 text-sm text-slate-600">
        <span className="flex items-center gap-1"><CalendarDays size={14} />{fmtDate(pkg.start_date)} → {fmtDate(pkg.end_date)}</span>
        <span className="flex items-center gap-1"><Users size={14} />{t.adults} adult{t.adults > 1 ? 's' : ''}{t.children > 0 && `, ${t.children} child${t.children > 1 ? 'ren' : ''}`}</span>
      </p>
      <p className="text-sm text-slate-600">{itemsOf(pkg, 'flight').length} flights · {itemsOf(pkg, 'hotel').length} stays · {itemsOf(pkg, 'transfer').length} transfers · {itemsOf(pkg, 'attraction').length} experiences</p>
      <div className="mt-auto flex flex-wrap items-end justify-between gap-3">
        <div><b className="text-2xl">{money(pkg.total_inr)}</b>
          <p className={`text-xs ${over ? 'text-red-600' : 'text-emerald-700'}`}>{over ? `${money(-pkg.remaining_inr)} over budget` : `${money(pkg.remaining_inr)} under budget`}</p></div>
        <a className="btn btn-primary" href={packageHash(pkg.trip_id)}>View details</a>
      </div>
    </div>
  </article>
}

export default function Results() {
  const [list] = useState(loadResults)
  const [sort, setSort] = useState('cheapest')
  const sorted = [...list].sort(SORTS[sort][1])
  return <main className="mx-auto max-w-5xl px-4 pb-16 pt-6">
    <a href="#/" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-600 hover:underline"><ArrowLeft size={15} />Edit search</a>
    {!list.length ? <div className="p-8 text-center"><p className="mb-4">No search yet.</p><a className="btn btn-primary" href="#/">Plan a trip</a></div> : <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{list.length} package{list.length > 1 ? 's' : ''} for {list[0].country}</h1>
        {list.length > 1 && <label className="flex items-center gap-2 text-sm">Sort
          <select className="select select-bordered select-sm" value={sort} onChange={e => setSort(e.target.value)}>
            {Object.entries(SORTS).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}</select></label>}
      </div>
      <Paginated key={sort} items={sorted} size={PAGE_SIZE} className="grid gap-5" render={p => <PackageCard key={p.trip_id} pkg={p} />} />
    </>}
  </main>
}
