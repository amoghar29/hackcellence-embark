import TripSearch from '../components/TripSearch'

export default function Landing() {
  return <main>
    <section className="relative isolate overflow-hidden bg-brand-deep px-4 pb-24 pt-16 text-white sm:pt-24">
      <img src="/images/tokyo.jpg" alt="" className="absolute inset-0 -z-10 h-full w-full object-cover opacity-40" />
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-4xl font-bold sm:text-5xl">Your whole holiday, planned in one search</h1>
        <p className="mt-3 text-lg text-white/85">Flights, stays, transfers and sightseeing, built around your dates and budget.</p>
      </div>
    </section>
    <section className="relative z-10 mx-auto -mt-16 max-w-3xl px-4 pb-16" aria-labelledby="plan-h">
      <div className="rounded-2xl bg-white p-6 text-ink shadow-xl sm:p-8">
        <h2 id="plan-h" className="mb-5 text-xl font-bold">Plan your trip</h2>
        <TripSearch />
      </div>
    </section>
  </main>
}
