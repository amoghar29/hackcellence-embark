// Getting around on the day: legs between the hotel and the visits (the backend works them out from
// Google travel times when they were fetched, else from distance), map routes and directions links.

export const mapsLink = (a, b) =>
  `https://www.google.com/maps/dir/?api=1&origin=${a.lat},${a.lng}&destination=${b.lat},${b.lng}&travelmode=driving`

const here = it => ({ lat: it.details.lat, lng: it.details.lng })

// How the traveler gets to this visit; null when the package has no legs (older saved packages).
export function legOf(it) {
  const t = it.type === 'attraction' && it.details?.travel_from
  if (!t) return null
  return { from: t.name, minutes: t.minutes, km: t.km, estimate: t.source !== 'google', link: mapsLink(t, here(it)) }
}

// The way back to the hotel, on the last visit of a day only.
export function backLegOf(it) {
  const t = it.type === 'attraction' && it.details?.travel_back
  if (!t) return null
  return { to: t.name, minutes: t.minutes, km: t.km, estimate: t.source !== 'google', link: mapsLink(here(it), t) }
}

export const coordsOf = pkg => Object.fromEntries(pkg.items
  .filter(i => i.details?.lat != null).map(i => [i.catalog_id, { lat: i.details.lat, lng: i.details.lng }]))

const byStart = (a, b) => a.start.localeCompare(b.start)

// One day on the map: the hotel of that night, the visits in order, and back to the hotel.
export function dayRoute(pkg, date) {
  const visits = pkg.items.filter(i => i.type === 'attraction' && i.start.slice(0, 10) === date && i.details?.lat != null).sort(byStart)
  const hotel = pkg.items.find(i => i.type === 'hotel' && i.start.slice(0, 10) <= date && date < i.end.slice(0, 10) && i.details?.lat != null)
  if (!visits.length) return []
  const point = item => ({ item, ...here(item) })
  return hotel ? [point(hotel), ...visits.map(point), point(hotel)] : visits.map(point)
}

// '10:00' + -15 -> '09:45' (wraps at midnight).
export function addMinutes(hhmm, minutes) {
  const m = ((Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5)) + minutes) % 1440 + 1440) % 1440
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}

// A day's visits read as a journey: when to leave the hotel, each leg (from -> visit), and when you are back.
// null when the visits carry no legs (older saved packages).
export function dayJourney(visits) {
  const day = [...visits].sort(byStart), first = day[0], last = day[day.length - 1]
  const go = first && legOf(first)
  if (!go) return null
  const home = backLegOf(last)
  return {
    leave: { time: addMinutes(first.start.slice(11, 16), -go.minutes), place: go.from },
    stops: day.map(to => ({ to, ...legOf(to) })).filter(s => s.from),
    back: home && { time: addMinutes(last.end.slice(11, 16), home.minutes), place: home.to },
  }
}

// Every attraction of the trip, grouped by day.
export function attractionsByDay(pkg) {
  const days = {}
  for (const it of pkg.items.filter(i => i.type === 'attraction').sort(byStart)) {
    (days[it.start.slice(0, 10)] ||= { date: it.start.slice(0, 10), city: it.city, items: [] }).items.push(it)
  }
  return Object.values(days).sort((a, b) => a.date.localeCompare(b.date))
}
