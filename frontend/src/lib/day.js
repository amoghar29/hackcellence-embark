// One day of a package, worked out for the day popup: each event with its duration, the hotel the day starts
// from and ends at, and the time spent visiting and travelling. Times are the package's local times.

const MINUTES = { ATTRACTION: d => d.visit_minutes, TRANSFER: d => d.duration_minutes, FLIGHT_DEPARTURE: d => d.duration_minutes }
const TRAVEL = new Set(['TRANSFER', 'FLIGHT_DEPARTURE'])
const toMin = t => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5))

export function dayView(pkg, day) {
  const byId = Object.fromEntries(pkg.items.map(i => [i.item_id, i]))
  const hotels = pkg.items.filter(i => i.type === 'hotel')
  const events = day.events.map(e => {
    const item = byId[e.item_id], f = MINUTES[e.kind]
    return { ...e, item, minutes: (item && f?.(item.details || {})) ?? null }
  }).sort((a, b) => a.time.localeCompare(b.time))
  const sum = pred => events.filter(pred).reduce((s, e) => s + (e.minutes || 0), 0)
  const starts = events.map(e => toMin(e.time))
  const ends = events.map(e => Math.min(24 * 60, toMin(e.time) + (e.minutes || 0)))
  const startAt = hotels.find(h => h.start.slice(0, 10) < day.date && day.date <= h.end.slice(0, 10)) || null
  const endAt = hotels.find(h => h.start.slice(0, 10) <= day.date && day.date < h.end.slice(0, 10)) || null
  const seen = new Set(), photos = []
  for (const it of [...events.filter(e => e.kind === 'ATTRACTION').map(e => e.item), startAt, endAt]) {
    const path = it?.details?.image
    if (path && !seen.has(path)) { seen.add(path); photos.push({ path, title: it.name, type: it.type }) }
  }
  return {
    events, startAt, endAt, photos,
    visitMinutes: sum(e => e.kind === 'ATTRACTION'),
    // transfers and flights, plus getting from the hotel to each visit and back
    travelMinutes: sum(e => TRAVEL.has(e.kind)) + events.filter(e => e.kind === 'ATTRACTION')
      .reduce((s, e) => s + (e.item?.details?.travel_from?.minutes || 0) + (e.item?.details?.travel_back?.minutes || 0), 0),
    cost: events.filter(e => e.kind in MINUTES).reduce((s, e) => s + (e.item?.price_inr || 0), 0),
    spanMinutes: events.length ? Math.max(...ends) - Math.min(...starts) : 0,
  }
}

// A day holds at most 2 experiences; a third needs one removed first.
export const dayFull = (pkg, date) =>
  (pkg.days.find(d => d.date === date)?.events.filter(e => e.kind === 'ATTRACTION').length ?? 0) >= 2

// The page's photos as one scrolling strip per section (stays, experiences).
export function photoSections(pkg) {
  return ['hotel', 'attraction'].map(type => {
    const seen = new Set()
    const photos = pkg.items.filter(i => i.type === type && i.details?.image && !seen.has(i.details.image) && seen.add(i.details.image))
      .map(i => ({ path: i.details.image, title: i.name, rating: i.details.rating ?? null, item: i }))
    return { type, photos }
  }).filter(s => s.photos.length)
}
