import { Search } from 'lucide-react'
import { reservationHash } from '../lib/route'

// Look up any booking by its reservation number; the reservation view handles "not found".
export default function FindBookingPage() {
  const submit = e => {
    e.preventDefault()
    const ref = new FormData(e.target).get('ref').trim()
    if (ref) window.location.hash = reservationHash(encodeURIComponent(ref))
  }
  return <main className="mx-auto max-w-xl px-4 pb-16 pt-8">
    <h1 className="text-2xl font-bold">Find a booking</h1>
    <p className="mt-1 text-slate-600">Enter the reservation number from your confirmation.</p>
    <form onSubmit={submit} className="mt-6 flex gap-2">
      <label htmlFor="ref" className="sr-only">Reservation number</label>
      <input id="ref" name="ref" required autoFocus className="input input-bordered flex-1 font-mono tracking-wider" placeholder="e.g. 4829105736" />
      <button className="btn btn-primary"><Search size={16} />Search</button>
    </form>
  </main>
}
