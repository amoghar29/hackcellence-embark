import { useState } from 'react'
import { Search } from 'lucide-react'
import { validateSearch, toRequest } from '../lib/validate'
import { parseBudget } from '../lib/format'

const FALLBACK = {
  departure_cities: [{ airport: 'BLR', city: 'Bengaluru' }, { airport: 'DEL', city: 'Delhi' }, { airport: 'BOM', city: 'Mumbai' }, { airport: 'MAA', city: 'Chennai' }],
  countries: ['Japan', 'United Arab Emirates'],
  rules: { min_nights: 3, max_nights: 10, first_night: '2027-04-01', last_departure: '2027-04-20' },
}

function Field({ label, error, hint, children, id }) {
  return <div>
    <label htmlFor={id} className="mb-1 block text-sm font-semibold text-slate-700">{label}</label>
    {children}
    {error ? <p id={`${id}-err`} role="alert" className="mt-1 text-sm text-red-600">{error}</p> : hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
  </div>
}
const cls = err => `input input-bordered w-full ${err ? 'input-error' : ''}`
const Stepper = ({ id, value, min, max, onChange, label }) => <div className="flex items-center gap-3">
  <button type="button" className="btn btn-circle btn-sm" aria-label={`Fewer ${label}`} disabled={value <= min} onClick={() => onChange(value - 1)}>−</button>
  <output id={id} className="w-6 text-center font-semibold">{value}</output>
  <button type="button" className="btn btn-circle btn-sm" aria-label={`More ${label}`} disabled={value >= max} onClick={() => onChange(value + 1)}>+</button>
</div>

export default function SearchForm({ options, form, setForm, onSubmit, loading, serverField }) {
  const o = options || FALLBACK
  const [touched, setTouched] = useState(false)
  const errors = validateSearch(form, o.rules)
  const shown = touched ? errors : {}
  const err = k => shown[k] || (serverField?.field === k ? serverField.error : '')
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const setKids = n => setForm(f => ({ ...f, child_ages: Array.from({ length: n }, (_, i) => f.child_ages[i] ?? 8) }))

  function submit(e) {
    e.preventDefault(); setTouched(true)
    if (Object.keys(errors).length) { document.querySelector('[aria-invalid="true"]')?.focus(); return }
    onSubmit(toRequest(form))
  }
  const a = (k, id) => ({ id, 'aria-invalid': !!err(k), 'aria-describedby': err(k) ? `${id}-err` : undefined })

  return <form onSubmit={submit} noValidate className="grid gap-5 sm:grid-cols-2">
    <Field id="dep" label="Flying from" error={err('departure_city')} hint="Any city or airport code. We tell you if there are no flights from it.">
      <input list="dep-cities" autoComplete="off" maxLength={60} className={cls(err('departure_city'))} value={form.departure_city} onChange={e => set('departure_city', e.target.value)} {...a('departure_city', 'dep')} />
      <datalist id="dep-cities">{o.departure_cities.map(c => <option key={c.airport} value={c.airport}>{c.city}</option>)}</datalist>
    </Field>
    <Field id="dest" label="Going to" error={err('country')}>
      <select className={`select select-bordered w-full ${err('country') ? 'select-error' : ''}`} value={form.country} onChange={e => set('country', e.target.value)} {...a('country', 'dest')}>
        {o.countries.map(c => <option key={c}>{c}</option>)}
      </select>
    </Field>
    <Field id="start" label="Arrival date" error={err('start_date')} hint={`Between ${o.rules.first_night} and ${o.rules.last_departure}`}>
      <input type="date" className={cls(err('start_date'))} min={o.rules.first_night} max={o.rules.last_departure} value={form.start_date} onChange={e => set('start_date', e.target.value)} {...a('start_date', 'start')} />
    </Field>
    <Field id="nights" label="Nights" error={err('nights')} hint={`${o.rules.min_nights}–${o.rules.max_nights} nights`}>
      <input type="number" inputMode="numeric" className={cls(err('nights'))} value={form.nights} onChange={e => set('nights', e.target.value)} {...a('nights', 'nights')} />
    </Field>
    <Field id="adults" label="Adults" error={err('adults')}>
      <Stepper id="adults" label="adults" value={Number(form.adults) || 0} min={1} max={10} onChange={v => set('adults', v)} />
    </Field>
    <Field id="kids" label="Children" error={err('child_ages')}>
      <Stepper id="kids" label="children" value={form.child_ages.length} min={0} max={6} onChange={setKids} />
    </Field>
    {form.child_ages.length > 0 && <fieldset className="sm:col-span-2">
      <legend className="mb-1 text-sm font-semibold text-slate-700">Children's ages (on the trip)</legend>
      <div className="flex flex-wrap gap-3">{form.child_ages.map((age, i) =>
        <select key={i} aria-label={`Age of child ${i + 1}`} className="select select-bordered select-sm" value={age}
          onChange={e => set('child_ages', form.child_ages.map((x, j) => j === i ? e.target.value : x))}>
          {Array.from({ length: 18 }, (_, n) => <option key={n} value={n}>{n === 0 ? 'Under 1' : `${n} yr`}</option>)}
        </select>)}</div>
    </fieldset>}
    <div className="sm:col-span-2">
      <Field id="budget" label="Total budget (₹, for everyone)" error={err('budget_inr')} hint="Flights, stays, transfers and experiences all count.">
        <input inputMode="numeric" placeholder="e.g. 3,50,000" className={cls(err('budget_inr'))} value={form.budget_inr}
          onChange={e => { const n = parseBudget(e.target.value.replace(/[^\d]/g, '')); set('budget_inr', n == null ? '' : n.toLocaleString('en-IN')) }} {...a('budget_inr', 'budget')} />
      </Field>
    </div>
    <button type="submit" disabled={loading} className="btn btn-primary btn-lg sm:col-span-2">
      {loading ? <><span className="loading loading-spinner" />Finding your trip…</> : <><Search size={18} />Find my trip</>}
    </button>
  </form>
}

export const initialForm = { departure_city: 'BLR', country: 'Japan', start_date: '2027-04-10', nights: 6, adults: 2, child_ages: [], budget_inr: '3,50,000' }
