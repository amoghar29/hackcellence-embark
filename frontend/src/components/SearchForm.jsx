import { useState } from 'react'
import { CalendarDays, MapPin, Moon, PlaneTakeoff, Search, Users, Wallet } from 'lucide-react'
import { validateSearch, toRequest } from '../lib/validate'
import { parseBudget } from '../lib/format'

const FALLBACK = {
  departure_cities: [{ airport: 'BLR', city: 'Bengaluru' }, { airport: 'DEL', city: 'Delhi' }, { airport: 'BOM', city: 'Mumbai' }, { airport: 'MAA', city: 'Chennai' }],
  countries: ['Japan', 'United Arab Emirates'],
  cities: { Japan: ['Tokyo', 'Kyoto', 'Osaka'], 'United Arab Emirates': ['Dubai', 'Abu Dhabi'] },
  themes: ['mixed', 'spiritual', 'adventure', 'culture'],
  rules: { min_nights: 3, max_nights: 10, first_night: '2027-04-01', last_departure: '2027-04-20' },
}

function Field({ label, error, hint, children, id }) {
  return <div>
    <label htmlFor={id} className="mb-1 block text-sm font-semibold text-slate-700">{label}</label>
    {children}
    {error ? <p id={`${id}-err`} role="alert" className="mt-1 text-sm text-red-600">{error}</p> : hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
  </div>
}
// Free-text input + filtered dropdown. Shows every city until the user types something that isn't an exact pick.
function CityPicker({ cities, value, onChange, className, ...aria }) {
  const [open, setOpen] = useState(false)
  const q = value.trim().toLowerCase()
  const exact = cities.some(c => c.airport.toLowerCase() === q || c.city.toLowerCase() === q)
  const list = exact || !q ? cities : cities.filter(c => `${c.airport} ${c.city}`.toLowerCase().includes(q))
  return <div className="relative">
    <input autoComplete="off" maxLength={60} role="combobox" aria-expanded={open} aria-controls="dep-list" placeholder="Search city or airport code"
      className={className} value={value} {...aria}
      onFocus={e => { setOpen(true); e.target.select() }} onBlur={() => setOpen(false)}
      onChange={e => { onChange(e.target.value); setOpen(true) }} onKeyDown={e => e.key === 'Escape' && setOpen(false)} />
    {open && list.length > 0 && <ul id="dep-list" role="listbox" className="menu absolute z-20 mt-1 max-h-60 w-full min-w-56 flex-nowrap overflow-auto rounded-box border bg-base-100 p-1 shadow-lg">
      {list.map(c => <li key={c.airport}>
        <button type="button" role="option" aria-selected={c.airport === value} onMouseDown={e => e.preventDefault()} onClick={() => { onChange(c.airport); setOpen(false) }}>
          <span className="font-semibold">{c.city}</span><span className="text-slate-500">{c.airport}</span>
        </button></li>)}
    </ul>}
  </div>
}
const clamp = (v, lo, hi) => String(Math.min(hi, Math.max(lo, Number(v) || lo)))
const cls = err => `input input-bordered w-full ${err ? 'input-error' : ''}`
const Stepper = ({ id, value, min, max, onChange, label }) => <div className="flex items-center gap-3">
  <button type="button" className="btn btn-circle btn-sm" aria-label={`Fewer ${label}`} disabled={value <= min} onClick={() => onChange(value - 1)}>−</button>
  <output id={id} className="w-6 text-center font-semibold">{value}</output>
  <button type="button" className="btn btn-circle btn-sm" aria-label={`More ${label}`} disabled={value >= max} onClick={() => onChange(value + 1)}>+</button>
</div>

// state, validation and submit shared by the full form (Landing) and the inline bar (Results)
function useSearchForm({ options, form, setForm, onSubmit, serverField }) {
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
  const firstError = Object.keys(form).map(err).find(Boolean) || ''
  return { o, err, set, setKids, submit, a, firstError }
}
const blockNonDigits = e => ['-', '+', 'e', 'E', '.'].includes(e.key) && e.preventDefault()
const setBudget = (set, v) => { const n = parseBudget(v.replace(/[^\d]/g, '')); set('budget_inr', n == null ? '' : n.toLocaleString('en-IN')) }
const ChildAges = ({ form, set }) => form.child_ages.map((age, i) =>
  <label key={i} className="flex items-center justify-between gap-2 text-sm font-medium text-slate-700">Child {i + 1}
    <input type="number" inputMode="numeric" min="0" max="17" step="1" aria-label={`Age of child ${i + 1}`} className="input input-bordered input-sm w-24"
      value={age} onKeyDown={blockNonDigits} onChange={e => set('child_ages', form.child_ages.map((x, j) => j === i ? e.target.value : x))} />
  </label>)

// One white segment of the search bar; clicking anywhere in it lands in its input.
const Cell = ({ icon: Icon, label, htmlFor, grow = "flex-1", children }) => <div className={`relative flex min-w-0 ${grow} items-center gap-2 rounded-lg bg-white px-3 py-1.5 focus-within:ring-2 focus-within:ring-primary`}>
  <Icon size={18} className="shrink-0 text-slate-500" />
  <div className="min-w-0 flex-1"><label htmlFor={htmlFor} className="block text-xs text-slate-500">{label}</label>{children}</div>
</div>
const bare = 'w-full bg-transparent text-sm font-semibold outline-none focus-visible:outline-none'

// booking.com-style bar: every field is edited in place, then Search.
export function SearchBar(props) {
  const { form, loading } = props
  const { o, err, set, setKids, submit, a, firstError } = useSearchForm(props)
  const kids = form.child_ages.length
  return <form onSubmit={submit} noValidate className="mb-8">
    <div className="flex flex-col gap-1 rounded-xl bg-amber-400 p-1 md:flex-row">
      <Cell icon={PlaneTakeoff} label="From" htmlFor="dep">
        <CityPicker cities={o.departure_cities} value={form.departure_city} onChange={v => set('departure_city', v)} className={bare} {...a('departure_city', 'dep')} />
      </Cell>
      <Cell icon={MapPin} label="Destination" htmlFor="dest" grow="flex-[1.2]">
        <select className={`${bare} cursor-pointer`} value={form.country} onChange={e => props.setForm(f => ({ ...f, country: e.target.value, cities: [] }))} {...a('country', 'dest')}>
          {o.countries.map(c => <option key={c}>{c}</option>)}
        </select>
      </Cell>
      <Cell icon={CalendarDays} label="Arrival" htmlFor="start">
        <input type="date" className={`${bare} cursor-pointer [&::-webkit-calendar-picker-indicator]:hidden`} onClick={e => e.target.showPicker?.()} min={o.rules.first_night} max={o.rules.last_departure} value={form.start_date} onChange={e => set('start_date', e.target.value)} {...a('start_date', 'start')} />
      </Cell>
      <Cell icon={Moon} label="Nights" htmlFor="nights" grow="flex-[0.8]">
        <select className={`${bare} cursor-pointer`} value={form.nights} onChange={e => set('nights', e.target.value)} {...a('nights', 'nights')}>
          {Array.from({ length: o.rules.max_nights - o.rules.min_nights + 1 }, (_, i) => o.rules.min_nights + i).map(n => <option key={n} value={n}>{n} nights</option>)}
        </select>
      </Cell>
      <Cell icon={Users} label="Travellers" htmlFor="trav" grow="flex-[1.3]">
        <details className="dropdown w-full">
          <summary id="trav" className={`${bare} cursor-pointer list-none truncate`} aria-invalid={!!(err('adults') || err('child_ages'))}>
            {form.adults} adult{form.adults > 1 ? 's' : ''} · {kids} child{kids === 1 ? '' : 'ren'}</summary>
          <div className="dropdown-content z-20 mt-3 grid w-64 gap-3 rounded-box border bg-base-100 p-4 shadow-lg">
            <div className="flex items-center justify-between text-sm font-semibold">Adults<Stepper id="adults" label="adults" value={Number(form.adults) || 0} min={1} max={10} onChange={v => set('adults', v)} /></div>
            <div className="flex items-center justify-between text-sm font-semibold">Children<Stepper id="kids" label="children" value={kids} min={0} max={6} onChange={setKids} /></div>
            <ChildAges form={form} set={set} />
          </div>
        </details>
      </Cell>
      <Cell icon={Wallet} label="Budget (₹)" htmlFor="budget">
        <input inputMode="numeric" className={bare} value={form.budget_inr} onChange={e => setBudget(set, e.target.value)} {...a('budget_inr', 'budget')} />
      </Cell>
      <button type="submit" disabled={loading} className="btn btn-primary h-auto min-h-10 rounded-lg px-5">
        {loading ? <span className="loading loading-spinner" /> : <Search size={18} />}Search</button>
    </div>
    {firstError && <p role="alert" className="mt-2 text-sm font-medium text-red-600">{firstError}</p>}
  </form>
}

export default function SearchForm(props) {
  const { form, loading, setForm } = props
  const { o, err, set, setKids, submit, a } = useSearchForm(props)

  return <form onSubmit={submit} noValidate className="grid gap-5 sm:grid-cols-2">
    <Field id="dep" label="Flying from" error={err('departure_city')} hint="Any city or airport code. We tell you if there are no flights from it.">
      <CityPicker cities={o.departure_cities} value={form.departure_city} onChange={v => set('departure_city', v)} className={cls(err('departure_city'))} {...a('departure_city', 'dep')} />
    </Field>
    <Field id="dest" label="Going to" error={err('country')}>
      <select className={`select select-bordered w-full ${err('country') ? 'select-error' : ''}`} value={form.country} onChange={e => setForm(f => ({ ...f, country: e.target.value, cities: [] }))} {...a('country', 'dest')}>
        {o.countries.map(c => <option key={c}>{c}</option>)}
      </select>
    </Field>
    <fieldset>
      <legend className="mb-1 block text-sm font-semibold text-slate-700">Cities to include (optional)</legend>
      <div className="flex flex-wrap gap-2">{(o.cities?.[form.country] || []).map(c => {
        const on = form.cities.includes(c)
        return <button key={c} type="button" aria-pressed={on} className={`btn btn-sm rounded-full ${on ? 'btn-primary' : 'btn-outline'}`}
          onClick={() => set('cities', on ? form.cities.filter(x => x !== c) : [...form.cities, c])}>{c}</button>
      })}</div>
      {err('cities') ? <p id="cities-err" role="alert" className="mt-1 text-sm text-red-600">{err('cities')}</p>
        : <p className="mt-1 text-xs text-slate-500">Every package visits these. None picked: we choose for you.</p>}
    </fieldset>
    <Field id="theme" label="Trip theme (optional)" error={err('theme')}>
      <select className="select select-bordered w-full" value={form.theme} onChange={e => set('theme', e.target.value)} {...a('theme', 'theme')}>
        {(o.themes || ['mixed']).map(t => <option key={t} value={t}>{t[0].toUpperCase() + t.slice(1)}</option>)}
      </select>
    </Field>
    <Field id="start" label="Arrival date" error={err('start_date')} hint={`Between ${o.rules.first_night} and ${o.rules.last_departure}`}>
      <input type="date" className={cls(err('start_date'))} min={o.rules.first_night} max={o.rules.last_departure} value={form.start_date} onChange={e => set('start_date', e.target.value)}
        onBlur={() => form.start_date && set('start_date', form.start_date < o.rules.first_night ? o.rules.first_night : form.start_date > o.rules.last_departure ? o.rules.last_departure : form.start_date)} {...a('start_date', 'start')} />
    </Field>
    <Field id="nights" label="Nights" error={err('nights')} hint={`${o.rules.min_nights}–${o.rules.max_nights} nights`}>
      <input type="number" inputMode="numeric" step={1} min={o.rules.min_nights} max={o.rules.max_nights} className={cls(err('nights'))} value={form.nights}
        onKeyDown={blockNonDigits}
        onChange={e => set('nights', e.target.value.replace(/\D/g, '').slice(0, 2))}
        onBlur={() => set('nights', clamp(form.nights, o.rules.min_nights, o.rules.max_nights))} {...a('nights', 'nights')} />
    </Field>
    <Field id="adults" label="Adults" error={err('adults')}>
      <Stepper id="adults" label="adults" value={Number(form.adults) || 0} min={1} max={10} onChange={v => set('adults', v)} />
    </Field>
    <Field id="kids" label="Children" error={err('child_ages')}>
      <Stepper id="kids" label="children" value={form.child_ages.length} min={0} max={6} onChange={setKids} />
    </Field>
    {form.child_ages.length > 0 && <fieldset className="sm:col-span-2">
      <legend className="mb-1 text-sm font-semibold text-slate-700">Children's ages (in years)</legend>
      <div className="grid max-w-xs grid-cols-1 gap-2"><ChildAges form={form} set={set} /></div>
    </fieldset>}
    <div className="sm:col-span-2">
      <Field id="budget" label="Total budget (₹, for everyone)" error={err('budget_inr')} hint="Flights, stays, transfers and experiences all count.">
        <input inputMode="numeric" placeholder="e.g. 3,50,000" className={cls(err('budget_inr'))} value={form.budget_inr}
          onChange={e => setBudget(set, e.target.value)} {...a('budget_inr', 'budget')} />
      </Field>
    </div>
    <button type="submit" disabled={loading} className="btn btn-primary btn-lg sm:col-span-2">
      {loading ? <><span className="loading loading-spinner" />Finding your trip…</> : <><Search size={18} />Find my trip</>}
    </button>
  </form>
}

export const initialForm = { departure_city: 'BLR', country: 'Japan', start_date: '2027-04-10', nights: 6, adults: 2, child_ages: [], budget_inr: '3,50,000', cities: [], theme: 'mixed' }
