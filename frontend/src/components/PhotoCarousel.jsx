import { useRef, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Img } from './ui'
import { API } from '../lib/api'
import { imageUrl } from '../lib/format'

// Native scroll-snap carousel: swipe on touch, arrows and dots on desktop.
export default function PhotoCarousel({ photos, className = 'h-64' }) {
  const box = useRef(null)
  const [i, setI] = useState(0)
  const go = n => { const el = box.current; if (!el) return; const k = Math.min(Math.max(n, 0), photos.length - 1); el.scrollTo({ left: k * el.clientWidth, behavior: 'smooth' }); setI(k) }
  if (!photos.length) return <Img src={null} className={`w-full ${className}`} />
  return <div className={`relative overflow-hidden bg-slate-200 ${className}`} role="group" aria-roledescription="carousel" aria-label="Trip photos">
    <div ref={box} onScroll={e => setI(Math.round(e.currentTarget.scrollLeft / e.currentTarget.clientWidth))} className="flex h-full snap-x snap-mandatory overflow-x-auto scroll-smooth [scrollbar-width:none]">
      {photos.map((p, k) => <figure key={p.path} className="relative h-full w-full shrink-0 snap-center" aria-label={`${k + 1} of ${photos.length}`}>
        <Img src={imageUrl(p.path, API)} alt={p.title} className="h-full w-full" />
        <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-3 pt-8 text-sm text-white">{p.title}</figcaption>
      </figure>)}
    </div>
    {photos.length > 1 && <>
      <button onClick={() => go(i - 1)} disabled={i === 0} aria-label="Previous photo" className="btn btn-circle btn-sm absolute left-2 top-1/2 -translate-y-1/2 disabled:hidden"><ChevronLeft size={18} /></button>
      <button onClick={() => go(i + 1)} disabled={i === photos.length - 1} aria-label="Next photo" className="btn btn-circle btn-sm absolute right-2 top-1/2 -translate-y-1/2 disabled:hidden"><ChevronRight size={18} /></button>
      <div className="absolute right-3 top-3 rounded-full bg-black/60 px-2 py-0.5 text-xs text-white">{i + 1} / {photos.length}</div>
    </>}
  </div>
}
