import { useEffect, useState } from 'react'
import { Compass } from 'lucide-react'
import Landing from './pages/Landing'
import Results from './pages/Results'
import PackagePage from './pages/PackagePage'
import BookingsPage from './pages/BookingsPage'
import FindBookingPage from './pages/FindBookingPage'
import Credits from './pages/Credits'
import { parseHash } from './lib/route'

export default function App() {
  const [route, setRoute] = useState(() => parseHash(window.location.hash))
  useEffect(() => {
    const on = () => { setRoute(parseHash(window.location.hash)); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return <div className="min-h-dvh bg-slate-50 text-ink">
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center px-4">
        <a href="#/" className="flex items-center gap-2 text-lg font-bold text-brand"><Compass size={22} />embark</a>
        <a href="#/find" className="ml-auto mr-4 text-sm font-semibold text-slate-600 hover:underline">Find booking</a>
        <a href="#/bookings" className=" text-sm font-semibold text-slate-600 hover:underline">My bookings</a>
      </div>
    </header>
    {route.name === 'results' && <Results />}
    {route.name === 'bookings' && <BookingsPage />}
    {route.name === 'find' && <FindBookingPage />}
    {route.name === 'home' && <Landing />}
    {route.name === 'credits' && <Credits />}
    {/* key forces a fresh load (and fresh booking key) when the trip or reservation changes */}
    {route.name === 'package' && <PackagePage key={route.id} id={route.id} />}
    {route.name === 'reservation' && <PackagePage key={route.ref} reference={route.ref} />}
    <footer className="mx-auto max-w-6xl px-4 py-6 text-xs text-slate-500">Photos from Wikimedia Commons, see <a className="link" href="#/credits">photo credits</a>.</footer>
  </div>
}
