import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Spinner, Paginated, TYPE_META } from './ui'
import { getDetail } from '../lib/api'
import { stopsInOrder } from '../lib/trip'
import { fmtDate } from '../lib/format'

const COLORS = { hotel: '#d97706', attraction: '#e11d48' }

// Hotels and attractions in trip order, numbered and joined by a route line.
// Package items carry no coordinates, so they come from the detail endpoints (once, when the tab opens).
export default function MapView({ pkg, onOpen }) {
  const [coords, setCoords] = useState(null)
  const [failed, setFailed] = useState(0)
  const el = useRef(null), map = useRef(null), markers = useRef({})

  useEffect(() => {
    const places = pkg.items.filter(i => i.type === 'hotel' || i.type === 'attraction')
    Promise.allSettled(places.map(i => getDetail(i.type, i.catalog_id).then(d => [i.catalog_id, d]))).then(rs => {
      setFailed(rs.filter(r => r.status === 'rejected').length)
      setCoords(Object.fromEntries(rs.filter(r => r.status === 'fulfilled').map(r => r.value)))
    })
  }, [pkg.items])

  const stops = coords ? stopsInOrder(pkg, coords) : []

  useEffect(() => {
    if (!coords || !el.current || !stops.length) return
    const m = L.map(el.current, { scrollWheelZoom: false })
    map.current = m
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '© OpenStreetMap contributors' }).addTo(m)
    const pts = stops.map(s => [s.lat, s.lng])
    L.polyline(pts, { color: '#143b66', weight: 3, dashArray: '6 6' }).addTo(m)
    markers.current = {}
    stops.forEach(s => {
      const icon = L.divIcon({ className: '', iconSize: [30, 30], iconAnchor: [15, 15],
        html: `<div style="background:${COLORS[s.item.type]};color:#fff;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-weight:700;border:2px solid #fff;box-shadow:0 1px 4px #0006">${s.n}</div>` })
      const pop = document.createElement('div')
      pop.append(Object.assign(document.createElement('b'), { textContent: s.item.name }), document.createElement('br'), `${fmtDate(s.date)} · ${s.time}`)
      markers.current[s.n] = L.marker([s.lat, s.lng], { icon, title: s.item.name }).bindPopup(pop).addTo(m)
    })
    m.fitBounds(pts, { padding: [40, 40], maxZoom: 14 })
    return () => { m.remove(); map.current = null }
  }, [coords])

  const focus = s => { map.current?.flyTo([s.lat, s.lng], 15); markers.current[s.n]?.openPopup(); el.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) }

  if (!coords) return <Spinner label="Placing your trip on the map…" />
  if (!stops.length) return <p className="rounded-xl bg-slate-50 p-6 text-slate-600">We couldn't load locations for this trip right now.</p>
  return <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
    <div>
      <div ref={el} className="h-[26rem] rounded-2xl border border-slate-200 lg:h-[34rem]" role="application" aria-label="Trip map" />
      {failed > 0 && <p className="mt-2 text-sm text-amber-700">{failed} place{failed > 1 ? 's' : ''} couldn't be shown on the map.</p>}
    </div>
    <div>
      <h3 className="mb-2 font-bold">In trip order</h3>
      <Paginated items={stops} size={6} className="grid gap-2" render={s => {
        const M = TYPE_META[s.item.type]
        return <div key={s.n} className="flex items-center gap-3 rounded-xl border border-slate-200 p-2">
          <button onClick={() => focus(s)} className="flex min-w-0 flex-1 items-center gap-3 text-left" aria-label={`Show ${s.item.name} on the map`}>
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-bold text-white" style={{ background: COLORS[s.item.type] }}>{s.n}</span>
            <span className="min-w-0"><span className="block truncate font-semibold">{s.item.name}</span><span className="text-xs text-slate-500">{M.label} · {fmtDate(s.date)} · {s.time}</span></span>
          </button>
          <button className="btn btn-xs btn-ghost" onClick={() => onOpen(s.item)}>Details</button>
        </div>
      }} />
    </div>
  </div>
}
