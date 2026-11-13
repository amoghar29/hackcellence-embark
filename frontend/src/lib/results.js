// A package has no id: the server keeps nothing until it is booked. Search results live in sessionStorage so they
// survive navigation to a package and back (and a refresh); a package the traveler changed is kept next to them,
// by its position in the results, until the next search.
import { duration } from './format.js'

const KEY = 'embark.results', EDITED = 'embark.edited'

export const normalize = r => Array.isArray(r?.packages) ? r.packages : [r]

const read = (key, fallback) => { try { return JSON.parse(sessionStorage.getItem(key)) ?? fallback } catch { return fallback } }
const write = (key, value) => { try { sessionStorage.setItem(key, JSON.stringify(value)) } catch { /* private mode: it just won't survive a refresh */ } }

// `found` is what search returned: { packages, picks } or one package.
export function saveResults(found) {
  write(KEY, { packages: normalize(found), picks: found?.picks || {} })
  write(EDITED, {})
}

export const loadResults = () => { const s = read(KEY, null); return Array.isArray(s) ? s : s?.packages || [] }
export const loadPicks = () => read(KEY, null)?.picks || {}

export const loadPackage = i => read(EDITED, {})[i] || loadResults()[i] || null
export const savePackage = (i, pkg) => write(EDITED, { ...read(EDITED, {}), [i]: pkg })

// The three best packages the server names: cheapest, fastest (least travel time), best rated (hotel stars).
export const PICKS = {
  cheapest: ['Cheapest', 'Lowest total price'],
  fastest: ['Fastest', 'Least time in the air and between cities'],
  best_rated: ['Best rated', 'Highest hotel stars per night'],
}
export const badgesFor = (picks, i) => Object.keys(PICKS).filter(k => picks?.[k] === i)
export const travelText = mins => duration(mins)

export const SORTS = {
  cheapest: ['Price: low to high', (a, b) => a.total_inr - b.total_inr],
  priciest: ['Price: high to low', (a, b) => b.total_inr - a.total_inr],
  fastest: ['Fastest first', (a, b) => a.travel_minutes - b.travel_minutes],
  best_rated: ['Best rated first', (a, b) => b.avg_stars - a.avg_stars],
  nights: ['Most nights', (a, b) => b.nights - a.nights],
}
