import { useMemo, useState } from 'react'
import { CalendarDays, Clock, Star, Users } from 'lucide-react'
import PhotoGrid from '../components/PhotoGrid'
import TripSearch from '../components/TripSearch'
import { SearchBar } from '../components/SearchForm'
import { Paginated } from '../components/ui'
import { badgesFor, loadPicks, loadResults, PICKS, SORTS, travelText } from '../lib/results'
import { carouselPhotos, itemsOf } from '../lib/trip'
import { fmtDate, money } from '../lib/format'
import { packageHash } from '../lib/route'

const PAGE_SIZE = 10

const Badges = ({ keys }) => keys.length > 0 && <span className="flex flex-wrap gap-1">{keys.map(k =>
  <span key={k} className="badge badge-primary badge-soft font-semibold" title={PICKS[k][1]}>{PICKS[k][0]}</span>)}</span>

const Measures = ({ pkg }) => <p className="flex flex-wrap gap-x-4 text-sm text-slate-600">
  <span className="flex items-center gap-1"><Clock size={14} />{travelText(pkg.travel_minutes)} travelling</span>
  <span className="flex items-center gap-1"><Star size={14} className="text-amber-500" />{itemsOf(pkg, 'hotel').map(h => `${h.details?.stars}★`).join(' · ')} hotels</span>
</p>

// G4: the three best packages the server picked. One package can win several, then it is shown once.
function Picks({ list, picks }) {
  const winners = [...new Set(Object.keys(PICKS).map(k => picks[k]).filter(n => n != null))]
  if (!winners.length) return null
  return <section aria-label="Best packages" className="mb-8">
    <h2 className="mb-3 text-lg font-bold">Our top picks</h2>
    <div className="grid gap-4 md:grid-cols-3">{winners.map(n => {
      const p = list[n], keys = badgesFor(picks, n)
      return <article key={n} className="flex flex-col gap-2 rounded-2xl border-2 border-primary/40 bg-white p-4">
        <Badges keys={keys} />
        <p className="text-sm text-slate-500">{keys.map(k => PICKS[k][1]).join(' · ')}</p>
        <h3 className="font-bold">{p.cities.map(c => c.city).join(' → ')}</h3>
        <Measures pkg={p} />
        <div className="mt-auto flex items-end justify-between gap-2 pt-2">
          <b className="text-xl">{money(p.total_inr)}</b>
          <a className="btn btn-primary btn-sm" href={packageHash(n)}>Choose</a>
        </div>
      </article>
    })}</div>
  </section>
}

// soft background behind each card's photo grid, cycled by package index
const TINTS = ['bg-sky-100', 'bg-amber-100', 'bg-emerald-100', 'bg-rose-100', 'bg-violet-100', 'bg-teal-100']

function PackageCard({ pkg, idx, badges }) {
  // all photos, shuffled once per card mount (not on every re-render); the grid pages them 6 at a time
  const photos = useMemo(() => carouselPhotos(pkg).sort(() => Math.random() - 0.5), [pkg])
  const over = pkg.remaining_inr < 0
  const t = pkg.traveler
  return <article className="grid overflow-hidden rounded-2xl border border-slate-200 bg-white md:grid-cols-[1fr_1.2fr]">
    <div className={`p-2 ${TINTS[idx % TINTS.length]}`}><PhotoGrid photos={photos} className="h-full grid-cols-3 grid-rows-2" cell="min-h-24" /></div>
    <div className="flex flex-col gap-3 p-5">
      <div>
        <Badges keys={badges} />
        <h2 className="text-xl font-bold">{pkg.cities.map(c => c.city).join(' → ')}</h2>
        <p className="text-sm text-slate-600">{pkg.country} · {pkg.nights} nights</p>
      </div>
      <p className="flex flex-wrap gap-x-4 text-sm text-slate-600">
        <span className="flex items-center gap-1"><CalendarDays size={14} />{fmtDate(pkg.start_date)} → {fmtDate(pkg.end_date)}</span>
        <span className="flex items-center gap-1"><Users size={14} />{t.adults} adult{t.adults > 1 ? 's' : ''}{t.children > 0 && `, ${t.children} child${t.children > 1 ? 'ren' : ''}`}</span>
      </p>
      <Measures pkg={pkg} />
      <p className="text-sm text-slate-600">{itemsOf(pkg, 'flight').length} flights · {itemsOf(pkg, 'hotel').length} stays · {itemsOf(pkg, 'transfer').length} transfers · {itemsOf(pkg, 'attraction').length} experiences</p>
      <div className="mt-auto flex flex-wrap items-end justify-between gap-3">
        <div><b className="text-2xl">{money(pkg.total_inr)}</b>
          <p className={`text-xs ${over ? 'text-red-600' : 'text-emerald-700'}`}>{over ? `${money(-pkg.remaining_inr)} over budget` : `${money(pkg.remaining_inr)} under budget`}</p></div>
        <a className="btn btn-primary" href={packageHash(idx)}>View details</a>
      </div>
    </div>
  </article>
}

export default function Results() {
  const [list, setList] = useState(loadResults)
  const [picks, setPicks] = useState(loadPicks)
  const reload = () => { setList(loadResults()); setPicks(loadPicks()); window.scrollTo(0, 0) }
  const [sort, setSort] = useState('cheapest')
  // a package has no id: its position in the list is what the package page opens
  const sorted = list.map((pkg, idx) => ({ pkg, idx })).sort((a, b) => SORTS[sort][1](a.pkg, b.pkg))
  return <main className="mx-auto max-w-5xl px-4 pb-16 pt-6">
    <TripSearch Form={SearchBar} onDone={reload} />
    {!list.length ? <div className="p-8 text-center"><p className="mb-4">No search yet.</p><a className="btn btn-primary" href="#/">Plan a trip</a></div> : <>
      <Picks list={list} picks={picks} />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{list.length} package{list.length > 1 ? 's' : ''} for {list[0].country}</h1>
        {list.length > 1 && <label className="flex items-center gap-2 text-sm">Sort
          <select className="select select-bordered select-sm" value={sort} onChange={e => setSort(e.target.value)}>
            {Object.entries(SORTS).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}</select></label>}
      </div>
      <Paginated key={sort} items={sorted} size={PAGE_SIZE} className="grid gap-5" render={({ pkg, idx }) => <PackageCard key={idx} pkg={pkg} idx={idx} badges={badgesFor(picks, idx)} />} />
    </>}
  </main>
}
