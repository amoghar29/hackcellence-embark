import { useEffect, useMemo, useRef, useState } from 'react'
import { bookingKey } from './lib/idempotency'
import { ArrowLeft, ArrowRight, ArrowUpDown, BadgeCheck, CalendarDays, Check, ChevronDown, CircleHelp, Compass, Heart, Hotel, Luggage, MapPin, Menu, Plane, Search, ShieldCheck, Star, Ticket, Users, Wallet, X } from 'lucide-react'
import { Button } from './components/ui/button'
import { Card, CardContent } from './components/ui/card'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const destinations = [
  { name: 'Tokyo', country: 'Japan', tag: 'Big city energy', image: '/images/tokyo.jpg', price: '₹48,900' },
  { name: 'Kyoto', country: 'Japan', tag: 'Culture & calm', image: '/images/kyoto.jpg', price: '₹42,500' },
  { name: 'Dubai', country: 'United Arab Emirates', tag: 'A little extra', image: '/images/dubai.jpg', price: '₹35,200' },
]
const money = value => `₹${Number(value || 0).toLocaleString('en-IN')}`
const prettyDate = value => value ? new Date(`${value}T12:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Choose dates'

function App() {
  const [options, setOptions] = useState(null)
  const [form, setForm] = useState({ departure_city: 'BLR', country: 'Japan', start_date: '2027-04-10', nights: 6, adults: 2, children: 0, budget_inr: 350000 })
  const [pkg, setPkg] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [booking, setBooking] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [toast, setToast] = useState('')
  const bookingKeys = useRef(bookingKey())

  useEffect(() => { fetch(`${API}/api/options`).then(r => r.ok ? r.json() : null).then(data => { if (data) setOptions(data) }).catch(() => {}) }, [])
  useEffect(() => { const id = window.location.hash.match(/package\/([^/?]+)/)?.[1]; if (id) loadPackage(id) }, [])

  async function loadPackage(id) {
    setLoading(true); setError(null)
    try { const response = await fetch(`${API}/api/packages/${id}`); const data = await response.json(); if (!response.ok) throw data; setPkg(data) }
    catch (e) { setError(e?.error || 'This trip could not be opened. Check that the API is running, then try again.') }
    finally { setLoading(false) }
  }
  async function searchTrips(event) {
    event?.preventDefault(); setLoading(true); setError(null); setPkg(null)
    try {
      const response = await fetch(`${API}/api/packages/search`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...form, nights: Number(form.nights), adults: Number(form.adults), child_ages: Array.from({ length: Number(form.children) }, () => 8), budget_inr: Number(String(form.budget_inr).replace(/\D/g, '')) }) })
      const data = await response.json(); if (!response.ok) throw data
      setPkg(data); window.location.hash = `package/${data.trip_id}`; window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (e) { setError(e?.error || 'We couldn’t build your trip. Make sure the Embark API is running and try again.'); window.location.hash = '' }
    finally { setLoading(false) }
  }
  async function bookTrip() {
    if (!pkg) return
    setBooking(true); setError(null)
    try { const response = await fetch(`${API}/api/packages/${pkg.trip_id}/book`, { method: 'POST', headers: { 'Idempotency-Key': bookingKeys.current.get(pkg.trip_id) } }); const data = await response.json(); if (!response.ok) throw data; bookingKeys.current.clear(); setPkg(data.package); setToast(`You’re booked! Reservation ${data.reference}`) }
    catch (e) { if (e?.code === 'IDEMPOTENCY_KEY_REUSED') bookingKeys.current.clear(); setError(e?.error || 'We couldn’t confirm this booking. Please try again.') }
    finally { setBooking(false) }
  }
  const items = pkg?.items || []
  const flights = items.filter(item => item.type === 'flight')
  const hotels = items.filter(item => item.type === 'hotel')
  const attractions = items.filter(item => item.type === 'attraction')
  const visibleItems = useMemo(() => showAll ? items : items.slice(0, 5), [items, showAll])
  const cities = pkg?.cities?.map(city => city.city).join(' · ') || pkg?.country
  const departureCities = options?.departure_cities || [{ airport: 'BLR', city: 'Bengaluru' }, { airport: 'DEL', city: 'Delhi' }, { airport: 'BOM', city: 'Mumbai' }, { airport: 'MAA', city: 'Chennai' }]

  function update(key, value) { setForm(prev => ({ ...prev, [key]: value })) }
  function startSearch(destination) { update('country', destination.country); document.querySelector('#trip-search')?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }

  return <div className="app-shell">
    <header className="navbar topbar"><a className="brand" href="#" onClick={() => { setPkg(null); window.location.hash = '' }}><span className="brand-mark"><Compass size={20}/></span>embark<span className="brand-period">.</span></a><nav className="desktop-nav"><a href="#destinations">Discover</a><a href="#how-it-works">How it works</a><a href="#help">Help</a></nav><div className="nav-actions"><button className="currency-pill" aria-label="Currency Indian Rupee">₹ <ChevronDown size={14}/></button><button className="mobile-menu" aria-label="Open menu"><Menu size={20}/></button></div></header>

    {!pkg && <>
      <section className="hero"><div className="hero-image"/><div className="hero-shade"/><div className="hero-content"><span className="eyebrow">YOUR NEXT GREAT STORY STARTS HERE</span><h1>Go places.<br/><em>Feel everything.</em></h1><p>Thoughtful holidays, made just for you.<br className="desktop-break"/> One search. Every detail taken care of.</p><div className="hero-trust"><span><ShieldCheck size={16}/> Your trip, thoughtfully planned</span><span><BadgeCheck size={16}/> No hidden surprises</span></div></div><div className="hero-stamp"><span>MADE FOR<br/>THE WAY<br/><b>YOU TRAVEL</b></span><ArrowRight size={18}/></div></section>
      <main className="home-main">
        <section className="search-card" id="trip-search"><div className="search-heading"><div><span className="section-kicker">LET’S PLAN SOMETHING GOOD</span><h2>Where are you dreaming of?</h2></div><span className="step-count"><span>01</span> / 01</span></div><form onSubmit={searchTrips} className="search-form">
          <label className="field"><span className="field-label"><Plane size={15}/> DEPARTURE</span><select value={form.departure_city} onChange={e => update('departure_city', e.target.value)} aria-label="Departure city">{departureCities.map(city => <option key={city.airport} value={city.airport}>{city.city}</option>)}</select></label>
          <label className="field destination-field"><span className="field-label"><MapPin size={15}/> DESTINATION</span><select value={form.country} onChange={e => update('country', e.target.value)} aria-label="Destination">{(options?.countries || ['Japan', 'United Arab Emirates']).map(country => <option key={country}>{country}</option>)}</select></label>
          <label className="field"><span className="field-label"><CalendarDays size={15}/> START DATE</span><input type="date" min={options?.rules?.first_night || '2027-04-01'} max={options?.rules?.last_departure || '2027-04-20'} value={form.start_date} onChange={e => update('start_date', e.target.value)} aria-label="Start date" required/></label>
          <label className="field compact-field"><span className="field-label"><Luggage size={15}/> NIGHTS</span><select value={form.nights} onChange={e => update('nights', e.target.value)} aria-label="Nights">{Array.from({ length: 8 }, (_, i) => i + 3).map(n => <option key={n} value={n}>{n} nights</option>)}</select></label>
          <label className="field compact-field"><span className="field-label"><Users size={15}/> TRAVELLERS</span><select value={form.adults} onChange={e => update('adults', e.target.value)} aria-label="Adults">{[1,2,3,4,5,6].map(n => <option key={n} value={n}>{n} adult{n > 1 ? 's' : ''}</option>)}</select></label>
          <label className="field compact-field"><span className="field-label"><Users size={15}/> CHILDREN</span><select value={form.children} onChange={e => update('children', e.target.value)} aria-label="Children">{[0,1,2,3,4].map(n => <option key={n} value={n}>{n} {n === 1 ? 'child' : 'children'}</option>)}</select></label>
          <label className="field compact-field budget-field"><span className="field-label"><Wallet size={15}/> TOTAL BUDGET</span><span className="budget-input-wrap"><span aria-hidden="true">₹</span><input type="number" step="any" inputMode="numeric" placeholder="Enter amount" value={form.budget_inr} onChange={e => update('budget_inr', e.target.value)} aria-label="Total budget in Indian rupees" required/></span></label>
          <Button type="submit" size="lg" className="search-button" disabled={loading}><Search size={19}/>{loading ? 'Finding your trip…' : 'Find my trip'}<ArrowRight size={17}/></Button>
        </form><div className="search-foot"><span><Check size={14}/> Flights, stays & experiences in one plan</span><button type="button" onClick={() => document.querySelector('#how-it-works')?.scrollIntoView({ behavior: 'smooth' })}><CircleHelp size={14}/> How it works</button><span className="powered-note">Built around your budget</span></div>
        </section>
        {error && <div role="alert" className="alert error-alert"><CircleHelp size={18}/><div><strong>We hit a little turbulence.</strong><p>{error}</p>{!pkg && <button type="button" onClick={searchTrips}>Try your search again <ArrowRight size={14}/></button>}</div><button className="alert-close" aria-label="Dismiss error" onClick={() => setError(null)}><X size={16}/></button></div>}
        <section className="destination-section" id="destinations"><div className="section-title-row"><div><span className="section-kicker">A LITTLE INSPIRATION</span><h2>Somewhere wonderful is waiting</h2><p>Places we’d go back to in a heartbeat.</p></div><button className="text-link" onClick={() => document.querySelector('#trip-search')?.scrollIntoView({ behavior: 'smooth' })}>Explore all destinations <ArrowRight size={15}/></button></div><div className="destination-grid">{destinations.map((destination, index) => <button className={`destination-card destination-${index + 1}`} key={destination.name} onClick={() => startSearch(destination)}><img src={destination.image} alt={`${destination.name} travel`} loading="lazy"/><span className="destination-glow"/><span className="destination-save"><Heart size={17}/></span><span className="destination-info"><small>{destination.country} <span>·</span> {destination.tag}</small><strong>{destination.name}</strong><span className="destination-price">Trips from <b>{destination.price}</b> <ArrowRight size={15}/></span></span><span className="destination-no">0{index + 1}</span></button>)}</div></section>
        <section className="promise-strip" id="how-it-works"><div><span className="section-kicker">A BETTER WAY TO GET AWAY</span><h3>We do the planning. You make the memories.</h3></div><div className="promise-point"><span>01</span><p><b>Tell us what you love</b><small>Your dates, your budget, your kind of trip.</small></p></div><div className="promise-point"><span>02</span><p><b>Get a trip that fits</b><small>Every detail checked and taken care of.</small></p></div><div className="promise-point"><span>03</span><p><b>Just show up</b><small>More daydreaming, less tab juggling.</small></p></div></section>
      </main>
    </>}

    {pkg && <main className="results-main"><button className="back-link" onClick={() => { setPkg(null); window.location.hash = '' }}><ArrowLeft size={16}/> Back to trip search</button><div className="results-header"><div><span className="section-kicker">YOUR TRIP, ALL TOGETHER</span><h1>Your {pkg.country} escape</h1><p>{cities} <span>·</span> {pkg.nights} nights <span>·</span> {prettyDate(pkg.start_date)} – {prettyDate(pkg.end_date)}</p></div><div className="results-status"><span className={`badge ${pkg.status === 'BOOKED' ? 'badge-success' : 'badge-warning'}`}>{pkg.status === 'BOOKED' ? 'Confirmed' : 'Ready for you'}</span><span>Trip ID <code>{pkg.trip_id}</code></span></div></div>
      {error && <div role="alert" className="alert error-alert"><CircleHelp size={18}/><p>{error}</p><button className="alert-close" onClick={() => setError(null)} aria-label="Dismiss"><X size={16}/></button></div>}
      <section className="trip-summary"><div className="summary-total"><span>YOUR TRIP TOTAL</span><strong>{money(pkg.total_inr)}</strong><small>for {pkg.traveler?.adults || form.adults} travellers · flights, stays & more</small></div><div className="summary-detail"><Wallet size={19}/><span><b>Within your budget</b><small>{money(pkg.remaining_inr)} left to spend</small></span></div><div className="summary-detail"><ShieldCheck size={19}/><span><b>Every detail checked</b><small>Made to fit your trip</small></span></div><Button onClick={bookTrip} disabled={booking || pkg.status === 'BOOKED'} size="lg" className="book-button">{booking ? 'Confirming…' : pkg.status === 'BOOKED' ? 'Trip confirmed' : 'Book this trip'}{!booking && <ArrowRight size={17}/>}</Button></section>
      {pkg.status === 'BOOKED' && pkg.reference && <div className="booking-confirm"><span className="confirm-check"><Check size={20}/></span><div><strong>You’re going to {pkg.country}!</strong><small>Your reservation number is <b>{pkg.reference}</b>. Keep it handy.</small></div><BadgeCheck size={22}/></div>}
      <div className="results-layout"><section className="itinerary-column"><div className="list-heading"><div><span className="section-kicker">THE GOOD STUFF</span><h2>Your trip at a glance</h2></div><span className="item-count">{items.length} details, all sorted</span></div><div className="itinerary-list">{visibleItems.map(item => <ItineraryCard key={item.item_id} item={item}/>)}{items.length > 5 && <button className="show-more" onClick={() => setShowAll(v => !v)}>{showAll ? 'Show less' : `See all ${items.length} trip details`} <ChevronDown size={16} className={showAll ? 'rotate' : ''}/></button>}{items.length === 0 && <div className="empty-card"><Compass size={23}/><p>Your trip details will appear here as soon as your package is ready.</p></div>}</div></section><aside className="trip-sidebar"><Card className="side-card"><CardContent><div className="side-head"><div><span className="section-kicker">YOUR LITTLE GETAWAY</span><h3>The details</h3></div><span className="side-icon"><Luggage size={18}/></span></div><div className="side-row"><span><MapPin size={16}/> Destination</span><b>{cities}</b></div><div className="side-row"><span><CalendarDays size={16}/> Your dates</span><b>{prettyDate(pkg.start_date)} <small>· {pkg.nights} nights</small></b></div><div className="side-row"><span><Users size={16}/> Travellers</span><b>{pkg.traveler?.adults || form.adults} adults{pkg.traveler?.children ? `, ${pkg.traveler.children} children` : ''}</b></div><div className="side-row"><span><Plane size={16}/> Flights</span><b>{flights.length} included</b></div><div className="side-row"><span><Hotel size={16}/> Stays</span><b>{hotels.length} included</b></div><div className="side-row"><span><Ticket size={16}/> Experiences</span><b>{attractions.length} included</b></div><div className="side-total"><span>Your trip total</span><b>{money(pkg.total_inr)}</b></div><div className="side-budget"><span>Budget left</span><b>{money(pkg.remaining_inr)}</b></div><button className="help-link" id="help"><CircleHelp size={15}/> Need a hand? We’re here for you.</button></CardContent></Card><div className="side-reassurance"><ShieldCheck size={19}/><span><b>A trip you can feel good about</b><small>Every flight, room & experience checked to fit.</small></span></div></aside></div><section className="credits-note">Travel photos courtesy of the original photographers. <a href={`${API}/api/credits`} target="_blank" rel="noreferrer">View photo credits <ArrowRight size={13}/></a></section>
      </main>}

    <footer className="footer"><a className="brand" href="#"><span className="brand-mark"><Compass size={18}/></span>embark<span className="brand-period">.</span></a><span>Go a little further. Come back a little different.</span><div><a href="#help">We’re here to help</a><span>© 2025 Embark</span></div></footer>
    {toast && <div className="toast toast-end toast-bottom"><div className="alert booking-toast"><Check size={18}/><span>{toast}</span><button onClick={() => setToast('')} aria-label="Dismiss notification"><X size={16}/></button></div></div>}
  </div>
}

function ItineraryCard({ item }) {
  const type = item.type
  const detail = item.details || {}
  const icon = type === 'flight' ? <Plane size={17}/> : type === 'hotel' ? <Hotel size={17}/> : type === 'attraction' ? <Ticket size={17}/> : <ArrowUpDown size={17}/>
  const title = item.name || (type === 'flight' ? `${detail.from_airport || ''} to ${detail.to_airport || ''}` : type)
  const date = (item.start || '').slice(0, 10)
  const subtitle = type === 'flight' ? `${detail.airline || ''} ${detail.flight_number || ''} · ${detail.direction === 'RETURN' ? 'Return flight' : 'Your flight there'}` : type === 'hotel' ? `${detail.area || item.city || ''}${detail.stars ? ` · ${'★'.repeat(detail.stars)}` : ''}${detail.room_name ? ` · ${detail.room_name}` : ''}` : type === 'attraction' ? `${detail.category || 'Experience'}${detail.visit_minutes ? ` · ${detail.visit_minutes} min` : ''}` : `${detail.kind === 'INTERCITY' ? 'Getting between cities' : 'Airport transfer'}${item.city ? ` · ${item.city}` : ''}`
  const image = type === 'hotel' ? detail.image : type === 'attraction' ? detail.image : null
  const imageSrc = image ? (image.startsWith('http') ? image : `${API}/${image.replace(/^\//, '')}`) : type === 'hotel' ? '/images/kyoto.jpg' : '/images/tokyo.jpg'
  return <Card className="itinerary-card"><div className={`item-image ${type}`}>{<img src={imageSrc} alt="" loading="lazy"/>}<span className="image-type">{icon}{type}</span></div><CardContent><div className="item-topline"><span className="item-date">{prettyDate(date)}</span><span className="item-status"><Check size={12}/> included</span></div><h3>{title}</h3><p className="item-subtitle">{subtitle}</p><div className="item-meta">{type === 'flight' && <span><Plane size={13}/>{detail.stops === 0 ? 'Non-stop' : `${detail.stops ?? 1} stop${detail.stops > 1 ? 's' : ''}`}</span>}{type === 'hotel' && <span><Star size={13}/>{detail.rating ? `${detail.rating} guest rating` : 'A lovely place to stay'}</span>}{type === 'attraction' && <span><MapPin size={13}/>{item.city}</span>}{type === 'transfer' && <span><ArrowUpDown size={13}/>Convenient transfer</span>}{item.end && <span><CalendarDays size={13}/>{type === 'hotel' ? `${detail.nights || ''} nights` : String(item.end).slice(11, 16) || 'Included'}</span>}</div></CardContent><div className="item-price"><span>{type === 'hotel' ? 'stay total' : type === 'flight' ? 'flight total' : 'included'}</span><b>{money(item.price_inr)}</b></div></Card>
}

export default App
