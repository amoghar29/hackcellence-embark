export const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Resolves with JSON; rejects with the backend error body ({code,error,field,...}) or a network error body.
async function call(path, opts) {
  let res
  try { res = await fetch(`${API}${path}`, opts) } catch { throw { code: 'NETWORK', error: "We can't reach the server. Check your connection and try again." } }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw { code: 'HTTP', error: 'Something went wrong. Please try again.', ...data }
  return data
}
const json = (method, body, headers) => ({ method, headers: { 'Content-Type': 'application/json', ...headers }, body: body && JSON.stringify(body) })

export const getOptions = () => call('/api/options')
export const search = body => call('/api/packages/results', json('POST', body))
export const getReservation = ref => call(`/api/reservations/${ref}`)
export const getReservations = () => call('/api/reservations')
export const getDetail = (type, id) => call(`/api/${type}s/${id}`)

// There is no package id: the server keeps nothing until booking, so each call sends the package's own
// request and selection back (docs/API.md).
// A booked package also sends its reference, so the seats and rooms it already holds count as free while changing it.
const sent = (pkg, extra) => ({ request: pkg.request, selection: pkg.selection, ...(pkg.reference && { reference: pkg.reference }), ...extra })
export const book = (pkg, key) => call('/api/bookings', json('POST', sent(pkg), { 'Idempotency-Key': key }))
export const getChangeOptions = (pkg, type, q) => call(`/api/packages/options/${type}s`, json('POST', sent(pkg, q)))
export const getCityPlans = pkg => call('/api/packages/options/city-plans', json('POST', sent(pkg)))
export const change = (pkg, one) => call('/api/packages/change', json('POST', sent(pkg, { change: one })))
export const getCredits = () => call('/api/credits')
