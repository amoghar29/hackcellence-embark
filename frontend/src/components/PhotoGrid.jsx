import { useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { Img, Modal } from './ui'
import PhotoCarousel from './PhotoCarousel'
import { API } from '../lib/api'
import { imageUrl } from '../lib/format'

const PAGE = 6

// Photo grid, 6 at a time with < > when there are more; a photo opens a full-size carousel at that photo.
export default function PhotoGrid({ photos, className = 'mt-6 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4', cell = 'aspect-[4/3]' }) {
  const [page, setPage] = useState(0)
  const [open, setOpen] = useState(null)
  if (photos.length < 2) return null
  const pages = Math.ceil(photos.length / PAGE)
  const arrow = 'btn btn-circle btn-sm absolute top-1/2 z-10 -translate-y-1/2 shadow'
  return <div className="relative h-full">
    <ul className={`grid gap-2 ${className}`} aria-label="Photo gallery">
      {photos.slice(page * PAGE, page * PAGE + PAGE).map((p, k) => <li key={p.path} className={`relative overflow-hidden rounded-xl bg-slate-200 ${cell}`}>
        <button onClick={() => setOpen(page * PAGE + k)} className="block h-full w-full" aria-label={`View ${p.title}`}>
          <Img src={imageUrl(p.path, API)} alt={p.title} className="h-full w-full transition hover:scale-105" />
          <span className="absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-black/70 to-transparent p-2 pt-6 text-left text-xs text-white">{p.title}</span>
        </button>
      </li>)}
    </ul>
    {page > 0 && <button onClick={() => setPage(page - 1)} aria-label="Previous photos" className={`${arrow} left-1`}><ChevronLeft size={18} /></button>}
    {page < pages - 1 && <button onClick={() => setPage(page + 1)} aria-label="More photos" className={`${arrow} right-1`}><ChevronRight size={18} /></button>}
    {open != null && <Modal label="Photo viewer" onClose={() => setOpen(null)} width="w-[min(60rem,calc(100%-2rem))]">
      <div className="relative">
        <PhotoCarousel photos={photos} start={open} className="h-[min(75vh,40rem)]" />
        <button onClick={() => setOpen(null)} aria-label="Close" className="btn btn-circle btn-sm absolute left-3 top-3"><X size={16} /></button>
      </div>
    </Modal>}
  </div>
}
