import { fmtDate, parseBudget } from './format.js'

const addDays = (iso, n) => { const d = new Date(`${iso}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10) }
const isInt = v => v !== '' && v != null && Number.isInteger(Number(v))

// Mirrors the backend rules (docs/API.md) so people fix mistakes before searching.
export function validateSearch(f, rules) {
  const e = {}
  if (!String(f.departure_city || '').trim()) e.departure_city = 'Enter the city you are flying from.'
  else if (f.departure_city.length > 60) e.departure_city = 'That city name is too long.'
  if (!f.country) e.country = 'Choose a destination.'
  const nightsOk = isInt(f.nights) && f.nights >= rules.min_nights && f.nights <= rules.max_nights
  if (!nightsOk) e.nights = `Nights must be a whole number from ${rules.min_nights} to ${rules.max_nights}.`
  if (!f.start_date) e.start_date = 'Pick your arrival date.'
  else if (f.start_date < rules.first_night) e.start_date = `Trips start on or after ${fmtDate(rules.first_night)}.`
  else if (nightsOk && addDays(f.start_date, Number(f.nights)) > rules.last_departure)
    e.start_date = `The trip must end by ${fmtDate(rules.last_departure)}. Start on or before ${fmtDate(addDays(rules.last_departure, -Number(f.nights)))}, or choose fewer nights.`
  if (!isInt(f.adults) || f.adults < 1) e.adults = 'At least 1 adult must travel.'
  if (f.child_ages.some(a => !isInt(a) || a < 0 || a > 17)) e.child_ages = 'Enter an age from 0 to 17 for every child.'
  const b = parseBudget(f.budget_inr)
  if (b == null) e.budget_inr = 'Enter your total budget in rupees.'
  else if (!Number.isInteger(b) || b <= 0) e.budget_inr = 'Budget must be a whole amount above ₹0.'
  return e
}

export const toRequest = f => ({
  departure_city: f.departure_city, country: f.country, start_date: f.start_date,
  nights: Number(f.nights), adults: Number(f.adults), child_ages: f.child_ages.map(Number), budget_inr: parseBudget(f.budget_inr),
})
