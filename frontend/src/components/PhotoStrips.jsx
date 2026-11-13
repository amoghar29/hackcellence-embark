import { useRef } from 'react'
import { ChevronLeft, ChevronRight, Star } from 'lucide-react'
import { Img, TYPE_META } from './ui'
import { API } from '../lib/api'
import { photoSections } from '../lib/day'
import { imageUrl } from '../lib/format'

// One horizontally scrolling strip per section (stays, experiences); a photo opens that place's details.
function Strip({ type, photos, onOpen }) {
  const box = useRef(null)
  const looping = type === 'attraction' && photos.length > 1
  const duration = `${photos.length * 5}s`
  return <section className="mt-6" aria-label={TYPE_META[type].plural}>
    <div className="mb-2 flex items-center justify-between">
      <h2 className="font-bold">{type === 'hotel' ? 'Your stays' : 'Your experiences'} <span className="font-normal text-slate-500">({photos.length})</span></h2>
      {!looping && photos.length > 2 && <div className="flex gap-1">
        <button className="btn btn-circle btn-sm" onClick={() => box.current?.scrollBy({ left: -box.current.clientWidth * 0.8, behavior: 'smooth' })} aria-label="Scroll back"><ChevronLeft size={16} /></button>
        <button className="btn btn-circle btn-sm" onClick={() => box.current?.scrollBy({ left: box.current.clientWidth * 0.8, behavior: 'smooth' })} aria-label="Scroll on"><ChevronRight size={16} /></button></div>}
    </div>
    <div className={looping ? 'overflow-hidden' : ''}>
    <ul ref={box} className={`flex pb-2 ${looping ? 'w-max animate-experiences-loop' : 'snap-x snap-mandatory gap-3 overflow-x-auto [scrollbar-width:thin]'}`} style={looping ? { '--loop-duration': duration } : undefined}>
    {[...(looping ? [0, 1] : [0])].map(copy => <li key={`group-${copy}`} aria-hidden={looping && copy === 1 ? true : undefined} className={`flex shrink-0 gap-3 ${looping ? 'pr-3' : ''}`}>{photos.map(p =>
      <div key={`${p.path}-${copy}`} className="w-60 shrink-0 snap-start sm:w-72"><button tabIndex={looping && copy === 1 ? -1 : undefined} onClick={() => onOpen(p.item)} className="relative block aspect-[4/3] w-full overflow-hidden rounded-xl bg-slate-200" aria-label={`Details of ${p.title}`}>
        <Img src={imageUrl(p.path, API)} alt={p.title} className="h-full w-full transition hover:scale-105" />
        {p.rating != null && <span className="absolute right-2 top-2 flex items-center gap-1 rounded-full bg-white/90 px-2 py-0.5 text-xs font-bold"><Star size={12} className="fill-amber-400 text-amber-500" />{p.rating}</span>}
        <span className="absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-black/70 to-transparent p-2 pt-6 text-left text-sm text-white">{p.title}</span>
      </button></div>)}</li>)}</ul>
    </div>
  </section>
}

export default function PhotoStrips({ pkg, onOpen }) {
  return photoSections(pkg).map(s => <Strip key={s.type} {...s} onOpen={onOpen} />)
}
