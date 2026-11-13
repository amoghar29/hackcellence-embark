const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const money = n => `${n < 0 ? '-' : ''}₹${Math.abs(Number(n) || 0).toLocaleString('en-IN')}`

export function parseBudget(v) {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null
  const s = String(v ?? '').replace(/[₹,\s]/g, '')
  return /^\d+(\.\d+)?$/.test(s) ? Number(s) : null
}

export function duration(mins) {
  const h = Math.floor(mins / 60), m = mins % 60
  return h ? (m ? `${h}h ${String(m).padStart(2, '0')}m` : `${h}h`) : `${m}m`
}

export function fmtDate(v) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v || '')
  return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}` : ''
}

export const fmtTime = v => (v || '').slice(11, 16)

export const imageUrl = (path, api) => !path ? null : /^https?:/.test(path) ? path : `${api}/${path.replace(/^\//, '')}`
