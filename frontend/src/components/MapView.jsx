import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Spinner } from './ui'
import { API, getDetail } from '../lib/api'
import { routeByDay, stopsInOrder } from '../lib/trip'
import { coordsOf, dayRoute, legOf } from '../lib/legs'
import { GOOGLE_KEY, loadGoogleMaps } from '../lib/gmaps'
import { duration, fmtDate, fmtTime, imageUrl } from '../lib/format'

const COLORS = { hotel: '#d97706', attraction: '#e11d48' }
// route colour per day (cycles on long trips); kept clear of the marker amber/rose
const DAY_COLORS = ['#2563eb', '#16a34a', '#9333ea', '#0891b2', '#ea580c', '#4f46e5', '#65a30d', '#db2777']

// The trip on a map: every hotel and experience in trip order, or one day (hotel → visits → hotel).
// Clicking a planned place shows its photo, time and how you get there; "Details" opens the full record.
// Coordinates come with the package; an older saved package fetches the missing ones from the detail endpoints.
export default function MapView({ pkg, onOpen, day: shown, onDay }) {
  const [coords, setCoords] = useState(null)
  // the page picks the day (clicking a day card); without a page that does, the map keeps its own choice
  const [own, setOwn] = useState('')
  const day = shown ?? own, setDay = onDay || setOwn
  const el = useRef(null)
  const visits = new Set(pkg.items.filter(i => i.type === 'attraction').map(i => i.start.slice(0, 10)))

  useEffect(() => {
    const known = coordsOf(pkg)
    const missing = pkg.items.filter(i => (i.type === 'hotel' || i.type === 'attraction') && !known[i.catalog_id])
    if (!missing.length) return setCoords(known)
    Promise.allSettled(missing.map(i => getDetail(i.type, i.catalog_id).then(d => [i.catalog_id, d]))).then(rs =>
      setCoords({ ...known, ...Object.fromEntries(rs.filter(r => r.status === 'fulfilled').map(r => r.value)) }))
  }, [pkg.items])

  const withCoords = coords && { ...pkg, items: pkg.items.map(i => coords[i.catalog_id] ? { ...i, details: { ...i.details, ...coords[i.catalog_id] } } : i) }
  // a day: hotel -> visits -> hotel; a day without visits: that night's hotel; else the whole trip in order
  const night = day && withCoords?.items.find(i => i.type === 'hotel' && i.start.slice(0, 10) <= day && day < i.end.slice(0, 10) && i.details?.lat != null)
  const route = day && withCoords ? dayRoute(withCoords, day) : []
  const stops = !withCoords ? [] : route.length
    ? route.map((p, n) => ({ ...p, n, date: day, time: p.item.type === 'attraction' ? fmtTime(p.item.start) : '' }))  // the hotel is home; visits 1, 2
    : night ? [{ item: night, lat: night.details.lat, lng: night.details.lng, n: 1, date: day, time: '' }]
    : stopsInOrder(withCoords, coords)
  const dayNo = d => pkg.days.findIndex(x => x.date === d)
  const colorOf = d => DAY_COLORS[Math.max(0, dayNo(d)) % DAY_COLORS.length]
  const lines = routeByDay(stops).map(l => ({ ...l, color: colorOf(l.date) }))

  // Google Maps (English) when the key works, else OpenStreetMap with English labels
  const [engine, setEngine] = useState(GOOGLE_KEY ? 'google' : 'osm')
  useEffect(() => {
    const fail = () => setEngine('osm')
    window.addEventListener('gmaps-failed', fail)
    return () => window.removeEventListener('gmaps-failed', fail)
  }, [])

  useEffect(() => {
    if (!coords || !el.current || !stops.length) return
    const markers = stops.filter((s, i) => stops.findIndex(o => o.item.item_id === s.item.item_id) === i)  // a day route returns to its hotel: one marker
    if (engine === 'google') {
      let gone = false
      loadGoogleMaps().then(g => { if (!gone) drawGoogle(g, el.current, lines, markers, day, onOpen) }).catch(() => !gone && setEngine('osm'))
      return () => { gone = true }
    }
    return drawLeaflet(el.current, stops, lines, markers, day, onOpen)
  }, [coords, day, engine])

  if (!coords) return <Spinner label="Placing your trip on the map…" />
  return <div>
    <label className="mb-2 flex items-center gap-2 text-sm">
      <span className="font-semibold">Show</span>
      <select className="select select-sm" value={day} onChange={e => setDay(e.target.value)} aria-label="Day to show on the map">
        <option value="">Whole trip</option>
        {pkg.days.map(({ date: d }, n) => <option key={d} value={d}>Day {n + 1} · {fmtDate(d)}{visits.has(d) ? ' route' : ''}</option>)}
      </select>
    </label>
    {!day && lines.length > 1 && <ul className="mb-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600" aria-label="Route colour by day">
      {lines.map(l => <li key={l.date} className="flex items-center gap-1">
        <span className="inline-block h-1 w-4 rounded" style={{ background: l.color }} />Day {dayNo(l.date) + 1}</li>)}
    </ul>}
    {stops.length ? <div key={`${day}-${engine}`} ref={el} className="h-[22rem] rounded-2xl border border-slate-200 lg:h-[calc(100dvh-9rem)]" role="application" aria-label="Trip map: hotels and experiences in order" />
      : <p className="rounded-xl bg-slate-50 p-6 text-slate-600">We couldn't load locations for this trip right now.</p>}
  </div>
}

function drawGoogle(g, node, lines, markers, day, onOpen) {
  const map = new g.Map(node, { mapTypeControl: false, streetViewControl: false, fullscreenControl: true, gestureHandling: 'cooperative' })
  lines.forEach(l => new g.Polyline({ map, path: l.pts.map(([lat, lng]) => ({ lat, lng })), strokeColor: l.color, strokeWeight: 3,
    strokeOpacity: day ? 1 : 0, icons: day ? [] : [{ icon: { path: 'M 0,-1 0,1', strokeOpacity: 1, scale: 3 }, offset: '0', repeat: '12px' }] }))
  const info = new g.InfoWindow(), bounds = new g.LatLngBounds()
  let home = null
  markers.forEach(s => {
    const hotel = s.item.type === 'hotel'
    const m = new g.Marker({ map, position: { lat: s.lat, lng: s.lng }, title: hotel ? `Home: ${s.item.name}` : s.item.name,
      label: { text: hotel ? '🏠' : String(s.n), color: '#fff', fontWeight: '700', fontSize: hotel ? '18px' : '14px' },
      zIndex: hotel ? 1000 : undefined,
      icon: { path: g.SymbolPath.CIRCLE, scale: hotel ? 19 : 14, fillColor: COLORS[s.item.type], fillOpacity: 1, strokeColor: '#fff', strokeWeight: hotel ? 3 : 2 } })
    const open = () => { info.setContent(popup(s, onOpen, !!day)); info.open({ map, anchor: m }) }
    m.addListener('click', open)
    if (day && hotel && !home) home = open
    bounds.extend(m.getPosition())
  })
  map.fitBounds(bounds, 40)
  if (home) g.event.addListenerOnce(map, 'idle', home)  // on a day, home is highlighted from the start
  g.event.addListenerOnce(map, 'idle', () => map.getZoom() > 14 && map.setZoom(14))
}

function drawLeaflet(node, stops, lines, markers, day, onOpen) {
  const m = L.map(node, { scrollWheelZoom: false })
  // CARTO's OpenStreetMap tiles label places in English (plain OSM tiles use the local script)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    { maxZoom: 18, subdomains: 'abcd', attribution: '© OpenStreetMap contributors © CARTO' }).addTo(m)
  const pts = stops.map(s => [s.lat, s.lng])
  lines.forEach(l => L.polyline(l.pts, { color: l.color, weight: 3, dashArray: day ? null : '6 6' }).addTo(m))
  let home = null
  markers.forEach(s => {
    const hotel = s.item.type === 'hotel', size = hotel ? 40 : 30
    const icon = L.divIcon({ className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
      html: `<div style="background:${COLORS[s.item.type]};color:#fff;width:${size}px;height:${size}px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:${hotel ? 20 : 14}px;border:${hotel ? 3 : 2}px solid #fff;box-shadow:0 1px 6px #0007">${hotel ? '🏠' : s.n}</div>` })
    const mk = L.marker([s.lat, s.lng], { icon, title: hotel ? `Home: ${s.item.name}` : s.item.name, keyboard: true, zIndexOffset: hotel ? 1000 : 0 })
      .bindPopup(popup(s, onOpen, !!day), { minWidth: 220 }).addTo(m)
    if (day && hotel && !home) home = mk
  })
  m.fitBounds(pts, { padding: [40, 40], maxZoom: 14 })
  home?.openPopup()  // on a day, home is highlighted from the start
  return () => m.remove()
}

// Built as DOM nodes (not an HTML string) so names from the catalog are never parsed as markup.
function popup(s, onOpen, oneDay) {
  const it = s.item, root = document.createElement('div'), add = (tag, props) => root.appendChild(Object.assign(document.createElement(tag), props))
  const photo = imageUrl(it.details?.image, API)
  if (photo) add('img', { src: photo, alt: '', style: 'width:100%;height:110px;object-fit:cover;border-radius:8px;margin-bottom:6px' })
  if (it.type === 'hotel' && oneDay) add('div', { textContent: '🏠 Home for the night: the day starts and ends here', style: 'color:#b45309;font-size:12px;font-weight:600' })
  add('b', { textContent: it.name })
  const when = it.type === 'attraction' ? `${fmtDate(it.start)} · ${fmtTime(it.start)}–${fmtTime(it.end)}` : `${fmtDate(it.start)} → ${fmtDate(it.end)}`
  add('div', { textContent: when, style: 'color:#475569;font-size:12px' })
  const leg = legOf(it)
  if (leg) add('div', { textContent: `~${duration(leg.minutes)} from ${leg.from} · ${leg.km} km`, style: 'color:#475569;font-size:12px' })
  if (onOpen) add('button', { textContent: 'Details', className: 'btn btn-xs btn-primary mt-2', onclick: () => onOpen(it) })
  return root
}
