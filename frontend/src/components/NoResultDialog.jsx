import { ArrowRight, Lightbulb, X } from 'lucide-react'
import { Modal, TYPE_META } from './ui'
import { money } from '../lib/format'

export default function NoResultDialog({ view, onClose, onTry }) {
  return <Modal onClose={onClose} label={view.title}>
    <div className="p-6">
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-xl font-bold">{view.title}</h2>
        <button className="btn btn-sm btn-circle btn-ghost" onClick={onClose} aria-label="Close"><X size={18} /></button>
      </div>

      {view.facts.length > 0 && <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
        {view.facts.map(f => <div key={f.label} className="rounded-xl bg-slate-50 p-3"><dt className="text-xs text-slate-500">{f.label}</dt><dd className="font-bold">{f.value}</dd></div>)}
      </dl>}

      {view.reasons.length > 0 && <ul className="mt-4 space-y-2">
        {view.reasons.map((r, i) => {
          const M = TYPE_META[r.part]
          return <li key={i} className="flex gap-3 rounded-xl bg-red-50 p-3 text-sm text-red-900">
            {M && <M.icon size={18} className="mt-0.5 shrink-0" aria-label={M.label} />}<span>{r.text}</span>
          </li>
        })}
      </ul>}

      {view.suggestion && <p className="mt-4 flex gap-2 text-sm text-slate-700"><Lightbulb size={18} className="shrink-0 text-amber-500" />{view.suggestion}</p>}

      {view.alternatives.length > 0 && <div className="mt-5">
        <h3 className="mb-2 text-sm font-semibold text-slate-700">Try one of these instead</h3>
        <div className="grid gap-2">{view.alternatives.map((a, i) =>
          <button key={i} onClick={() => onTry(a.change)} className="btn btn-outline h-auto justify-between py-3 text-left normal-case">
            <span>{a.label}</span><span className="flex items-center gap-1 font-bold">{money(a.total_inr)}<ArrowRight size={16} /></span>
          </button>)}</div>
      </div>}

      <button className="btn btn-ghost mt-5 w-full" onClick={onClose}>Edit my search</button>
    </div>
  </Modal>
}
