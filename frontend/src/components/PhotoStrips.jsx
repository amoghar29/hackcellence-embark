import { useRef } from 'react'
import { ChevronLeft, ChevronRight, Star } from 'lucide-react'
import { Img, TYPE_META } from './ui'
import { API } from '../lib/api'
import { photoSections } from '../lib/day'
import { imageUrl } from '../lib/format'

// One horizontally scrolling strip per section (stays, experiences); a photo opens that place's details.
function Strip({ type, photos, onOpen }) {
  const box = useRef(null)
  const go = dir => box.current?.scrollBy({ left: dir * box.current.clientWidth * 0.8, behavior: 'smooth' })
  return <section className="mt-6" aria-label={TYPE_META[type].plural}>
    <div className="mb-2 flex items-center justify-between">
      <h2 className="font-bold">{type === 'hotel' ? 'Your stays' : 'Your experiences'} <span className="font-normal text-slate-500">({photos.length})</span></h2>
      {photos.length > 2 && <div className="flex gap-1">
        <button className="btn btn-circle btn-sm" onClick={() => go(-1)} aria-label="Scroll back"><ChevronLeft size={16} /></button>
        <button className="btn btn-circle btn-sm" onClick={() => go(1)} aria-label="Scroll on"><ChevronRight size={16} /></button></div>}
    </div>
    <ul ref={box} className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2 [scrollbar-width:thin]">{photos.map(p =>
      <li key={p.path} className="w-60 shrink-0 snap-start sm:w-72"><button onClick={() => onOpen(p.item)} className="relative block aspect-[4/3] w-full overflow-hidden rounded-xl bg-slate-200" aria-label={`Details of ${p.title}`}>
        <Img src={imageUrl(p.path, API)} alt={p.title} className="h-full w-full transition hover:scale-105" />
        {p.rating != null && <span className="absolute right-2 top-2 flex items-center gap-1 rounded-full bg-white/90 px-2 py-0.5 text-xs font-bold"><Star size={12} className="fill-amber-400 text-amber-500" />{p.rating}</span>}
        <span className="absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-black/70 to-transparent p-2 pt-6 text-left text-sm text-white">{p.title}</span>
      </button></li>)}</ul>
  </section>
}

export default function PhotoStrips({ pkg, onOpen }) {
  return photoSections(pkg).map(s => <Strip key={s.type} {...s} onOpen={onOpen} />)
}
