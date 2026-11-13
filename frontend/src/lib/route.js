export const resultsHash = '#/results'
export const bookingsHash = '#/bookings'
export const packageHash = id => `#/package/${id}`
export const reservationHash = ref => `#/reservation/${ref}`

export function parseHash(hash) {
  if (/^#\/?results/.test(hash || '')) return { name: 'results' }
  if (/^#\/?bookings/.test(hash || '')) return { name: 'bookings' }
  const m = /^#\/?(package|reservation)\/([^/?]+)/.exec(hash || '')
  if (!m) return { name: 'home' }
  return m[1] === 'package' ? { name: 'package', id: m[2] } : { name: 'reservation', ref: m[2] }
}
