import { fmtDate, money } from './format.js'

export const TYPES = ['flight', 'hotel', 'transfer', 'attraction']
export const itemsOf = (pkg, type) => (pkg?.items || []).filter(i => i.type === type)

export function altLabel(c) {
  const parts = []
  if (c.start_date) parts.push(`Start on ${fmtDate(c.start_date)}`)
  if (c.departure_city) parts.push(`Fly from ${c.departure_city}`)
  if (c.nights) parts.push(`Take ${c.nights} nights`)
  if (c.budget_inr) parts.push(`Raise budget to ${money(c.budget_inr)}`)
  return parts.join(' · ')
}

// Turns a 422 NO_PACKAGE / OVER_BUDGET body into what the "no packages" popup shows.
export function noResultView(err) {
  const over = err.code === 'OVER_BUDGET'
  const reasons = err.blockers?.length ? err.blockers.map(b => ({ text: b.message, part: b.part }))
    : (err.reasons?.length ? err.reasons : [err.error]).map(text => ({ text, part: null }))
  return {
    kind: err.code,
    title: over ? 'Your budget is a little short' : "We couldn't build a trip for these choices",
    facts: over ? [{ label: 'Your budget', value: money(err.budget_inr) }, { label: 'Cheapest trip', value: money(err.cheapest_total_inr) }, { label: 'Short by', value: money(err.over_by_inr) }] : [],
    reasons: over ? [] : reasons,
    suggestion: err.suggestion || '',
    alternatives: (err.alternatives || []).map(a => ({ label: altLabel(a.change), change: a.change, total_inr: a.total_inr })),
  }
}

// Map stops in trip order: hotel at check-in, attractions by time. `details` = catalog_id -> {lat,lng}.
export function stopsInOrder(pkg, details) {
  const byId = Object.fromEntries((pkg.items || []).map(i => [i.item_id, i]))
  const out = []
  for (const day of pkg.days || []) {
    for (const ev of day.events || []) {
      if (ev.kind !== 'CHECK_IN' && ev.kind !== 'ATTRACTION') continue
      const item = byId[ev.item_id], d = item && details[item.catalog_id]
      if (d?.lat == null) continue
      out.push({ n: out.length + 1, item, lat: d.lat, lng: d.lng, date: day.date, time: ev.time })
    }
  }
  return out
}

// What changed between two package versions, for the "you changed X" banner.
export function changeSummary(before, after) {
  const afterById = Object.fromEntries(after.items.map(i => [i.item_id, i]))
  const beforeIds = new Set(before.items.map(i => i.item_id))
  const changed = [], removed = []
  for (const b of before.items) {
    const a = afterById[b.item_id]
    if (!a) removed.push(b)
    else if (a.catalog_id !== b.catalog_id) changed.push({ type: b.type, from: b.name, to: a.name })
  }
  const added = after.items.filter(i => !beforeIds.has(i.item_id))
  for (const r of removed) {
    const k = added.findIndex(a => a.type === r.type && a.city === r.city)
    if (k >= 0) changed.push({ type: r.type, from: r.name, to: added.splice(k, 1)[0].name })
    else changed.push({ type: r.type, from: r.name, to: null })
  }
  for (const a of added) changed.push({ type: a.type, from: null, to: a.name })
  return { changed, totalBefore: before.total_inr, totalAfter: after.total_inr, delta: after.total_inr - before.total_inr }
}

export const priceBreakdown = items => items.reduce((s, i) => ({ ...s, [i.type]: (s[i.type] || 0) + i.price_inr }), { flight: 0, hotel: 0, transfer: 0, attraction: 0 })

export function carouselPhotos(pkg) {
  const seen = new Set()
  return (pkg.items || []).flatMap(i => {
    const path = i.details?.image
    if (!path || seen.has(path)) return []
    seen.add(path)
    return [{ path, title: i.name, type: i.type }]
  })
}
