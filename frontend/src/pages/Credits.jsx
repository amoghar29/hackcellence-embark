import { useEffect, useState } from 'react'
import { getCredits } from '../lib/api'

// Renders the backend's ATTRIBUTIONS.md: intro paragraphs plus its table rows ("| file | place | source | author | license |").
const link = /\[([^\]]+)\]\(([^)]+)\)/
const cell = c => { const m = link.exec(c); return m ? <a className="link" href={m[2]} target="_blank" rel="noreferrer">{m[1]}</a> : c }

export default function Credits() {
  const [md, setMd] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { getCredits().then(r => setMd(r.markdown)).catch(e => setErr(e.error || 'Could not load photo credits.')) }, [])

  const lines = (md || '').split('\n')
  const rows = lines.filter(l => l.startsWith('|')).slice(2).map(l => l.split('|').slice(1, -1).map(s => s.trim()))
  const intro = lines.filter(l => l.trim() && !l.startsWith('|') && !l.startsWith('#'))

  return <main className="mx-auto max-w-6xl px-4 py-8">
    <h1 className="text-2xl font-bold">Photo credits</h1>
    {err && <p role="alert" className="mt-4 text-red-700">{err}</p>}
    {!md && !err && <p className="mt-4 text-slate-500">Loading…</p>}
    {intro.map((p, i) => <p key={i} className="mt-3 text-slate-600">{p}</p>)}
    {rows.length > 0 && <div className="mt-6 overflow-x-auto"><table className="table table-sm">
      <thead><tr><th>Used for</th><th>Source</th><th>Author</th><th>License</th></tr></thead>
      <tbody>{rows.map(r => <tr key={r[0]}>{r.slice(1).map((c, i) => <td key={i}>{cell(c)}</td>)}</tr>)}</tbody>
    </table></div>}
  </main>
}
