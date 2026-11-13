import { useEffect, useState } from 'react'
import { CircleAlert } from 'lucide-react'
import SearchForm, { initialForm } from '../components/SearchForm'
import NoResultDialog from '../components/NoResultDialog'
import { getOptions, search } from '../lib/api'
import { noResultView } from '../lib/trip'
import { resultsHash } from '../lib/route'
import { normalize, saveResults } from '../lib/results'

export default function Landing() {
  const [options, setOptions] = useState(null)
  const [form, setForm] = useState(initialForm)
  const [loading, setLoading] = useState(false)
  const [noResult, setNoResult] = useState(null)
  const [fieldError, setFieldError] = useState(null)
  const [fatal, setFatal] = useState('')

  useEffect(() => { getOptions().then(setOptions).catch(() => {}) }, [])

  async function run(body) {
    setLoading(true); setFatal(''); setFieldError(null); setNoResult(null)
    try { saveResults(normalize(await search(body))); window.location.hash = resultsHash }
    catch (e) {
      if (e.code === 'NO_PACKAGE' || e.code === 'OVER_BUDGET') setNoResult(noResultView(e))
      else if (e.code === 'INVALID_REQUEST' && e.field) setFieldError(e)
      else setFatal(e.error)
    } finally { setLoading(false) }
  }

  // "Try this" on a suggestion: apply the change to the form, then search again.
  function tryAlternative(change) {
    const next = { ...form, ...change }
    if (change.budget_inr) next.budget_inr = change.budget_inr.toLocaleString('en-IN')
    setForm(next)
    const ages = next.child_ages.map(Number)
    run({ departure_city: next.departure_city, country: next.country, start_date: next.start_date, nights: Number(next.nights), adults: Number(next.adults), child_ages: ages, budget_inr: Number(String(next.budget_inr).replace(/,/g, '')) })
  }

  return <main>
    <section className="relative isolate overflow-hidden bg-brand-deep px-4 pb-24 pt-16 text-white sm:pt-24">
      <img src="/images/tokyo.jpg" alt="" className="absolute inset-0 -z-10 h-full w-full object-cover opacity-40" />
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-4xl font-bold sm:text-5xl">Your whole holiday, planned in one search</h1>
        <p className="mt-3 text-lg text-white/85">Flights, stays, transfers and sightseeing, built around your dates and budget.</p>
      </div>
    </section>
    <section className="relative z-10 mx-auto -mt-16 max-w-3xl px-4 pb-16" aria-labelledby="plan-h">
      <div className="rounded-2xl bg-white p-6 text-ink shadow-xl sm:p-8">
        <h2 id="plan-h" className="mb-5 text-xl font-bold">Plan your trip</h2>
        {fatal && <div role="alert" className="alert alert-error mb-5"><CircleAlert size={18} />{fatal}</div>}
        <SearchForm options={options} form={form} setForm={f => { setForm(f); setFieldError(null) }} onSubmit={run} loading={loading} serverField={fieldError} />
      </div>
    </section>
    {noResult && <NoResultDialog view={noResult} onClose={() => setNoResult(null)} onTry={tryAlternative} />}
  </main>
}
