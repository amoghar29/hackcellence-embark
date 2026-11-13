import { useEffect, useState } from 'react'
import { CircleAlert } from 'lucide-react'
import SearchForm, { initialForm } from './SearchForm'
import NoResultDialog from './NoResultDialog'
import { getOptions, search } from '../lib/api'
import { noResultView } from '../lib/trip'
import { resultsHash } from '../lib/route'
import { loadForm, saveForm, saveResults } from '../lib/results'
import { toRequest } from '../lib/validate'

// The search form plus everything around running it. Used on Landing and, prefilled, on Results ("Edit search").
export default function TripSearch({ Form = SearchForm, onDone = () => { window.location.hash = resultsHash } }) {
  const [options, setOptions] = useState(null)
  const [form, setForm] = useState(() => loadForm() || initialForm)
  const [loading, setLoading] = useState(false)
  const [noResult, setNoResult] = useState(null)
  const [fieldError, setFieldError] = useState(null)
  const [fatal, setFatal] = useState('')

  useEffect(() => { getOptions().then(setOptions).catch(() => {}) }, [])

  async function run(f) {
    setLoading(true); setFatal(''); setFieldError(null); setNoResult(null)
    try { saveResults(await search(toRequest(f))); saveForm(f); onDone() }
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
    run(next)
  }

  return <>
    {fatal && <div role="alert" className="alert alert-error mb-5"><CircleAlert size={18} />{fatal}</div>}
    <Form options={options} form={form} setForm={f => { setForm(f); setFieldError(null) }} onSubmit={() => run(form)} loading={loading} serverField={fieldError} />
    {noResult && <NoResultDialog view={noResult} onClose={() => setNoResult(null)} onTry={tryAlternative} />}
  </>
}
