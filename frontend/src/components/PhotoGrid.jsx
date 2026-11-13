import { Img } from './ui'
import { API } from '../lib/api'
import { imageUrl } from '../lib/format'

export default function PhotoGrid({ photos, className = 'mt-6 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4', cell = 'aspect-[4/3]' }) {
  if (photos.length < 2) return null
  return <ul className={`grid gap-2 ${className}`} aria-label="Photo gallery">
    {photos.map(p => <li key={p.path} className={`relative overflow-hidden rounded-xl bg-slate-200 ${cell}`}>
      <Img src={imageUrl(p.path, API)} alt={p.title} className="h-full w-full" />
      <span className="absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-black/70 to-transparent p-2 pt-6 text-xs text-white">{p.title}</span>
    </li>)}
  </ul>
}
