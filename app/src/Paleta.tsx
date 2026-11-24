import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Conversa, type ReceitaResumo } from './api'
import { Icone } from './Icones'

// Paleta de comandos (16/11/2026): Ctrl+K (ou ⌘K) abre; digita, setas, Enter. Junta páginas, conversas recentes e receitas de edição num lugar só.
type Item = { id: string; grupo: string; rotulo: string; sub?: string; icone: string; ir: () => void }
const sem = (t: string) => t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export function Paleta({ paginas, conversas }: { paginas: { to: string; rotulo: string; icone: string }[]; conversas: Conversa[] }) {
  const nav = useNavigate()
  const [aberta, setAberta] = useState(false); const [q, setQ] = useState(''); const [sel, setSel] = useState(0)
  const [receitas, setReceitas] = useState<ReceitaResumo[]>([])
  const input = useRef<HTMLInputElement>(null); const listaRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setAberta(a => !a) } }
    const abrir = () => setAberta(true)
    window.addEventListener('keydown', k); window.addEventListener('gs-paleta', abrir)
    return () => { window.removeEventListener('keydown', k); window.removeEventListener('gs-paleta', abrir) }
  }, [])
  useEffect(() => { if (aberta) { setQ(''); setSel(0); setTimeout(() => input.current?.focus(), 10); if (!receitas.length) api.receitas().then(r => setReceitas(r.receitas)).catch(() => {}) } }, [aberta])
  const fechar = () => setAberta(false)
  const itens = useMemo<Item[]>(() => {
    const ir = (f: () => void) => () => { fechar(); f() }
    const todos: Item[] = [
      ...paginas.map(p => ({ id: `p${p.to}`, grupo: 'Ir para', rotulo: p.rotulo, icone: p.icone, ir: ir(() => nav(p.to)) })),
      ...conversas.slice(0, 40).map(c => ({ id: `c${c.id}`, grupo: 'Conversas', rotulo: c.titulo, sub: c.codigo, icone: 'conversa', ir: ir(() => nav(`/c/${c.id}`)) })),
      ...receitas.map(r => ({ id: `r${r.id}`, grupo: 'Novo pedido com receita', rotulo: r.nome, sub: r.resumo, icone: 'receitas', ir: ir(() => nav('/', { state: { receita: r.id, estilo: r.base_estilo } })) })),
    ]
    const t = sem(q.trim())
    if (!t) return [...todos.filter(i => i.grupo === 'Ir para').slice(0, 8), ...todos.filter(i => i.grupo === 'Conversas').slice(0, 5), ...todos.filter(i => i.grupo !== 'Ir para' && i.grupo !== 'Conversas').slice(0, 4)]
    return todos.filter(i => t.split(/\s+/).every(w => sem(`${i.rotulo} ${i.sub || ''}`).includes(w))).slice(0, 30)
  }, [q, paginas, conversas, receitas])
  useEffect(() => { setSel(0) }, [q])
  useEffect(() => { listaRef.current?.querySelector(`[data-i="${sel}"]`)?.scrollIntoView({ block: 'nearest' }) }, [sel])
  if (!aberta) return null
  const tecla = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') fechar()
    else if (e.key === 'ArrowDown') { e.preventDefault(); setSel(s => Math.min(itens.length - 1, s + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel(s => Math.max(0, s - 1)) }
    else if (e.key === 'Enter') itens[sel]?.ir()
  }
  let grupoAnterior = ''
  return <div className="fixed inset-0 z-[60] flex items-start justify-center bg-black/55 p-4 pt-[12vh] backdrop-blur-sm" onClick={fechar}>
    <div onClick={e => e.stopPropagation()} className="w-full max-w-xl overflow-hidden rounded-[20px] border border-white/10 bg-[#071030] shadow-2xl shadow-black/60">
      <div className="flex items-center gap-3 border-b border-white/5 px-4"><Icone nome="busca" className="h-5 w-5 text-nevoa" />
        <input ref={input} value={q} onChange={e => setQ(e.target.value)} onKeyDown={tecla} placeholder="Ir para página, conversa ou receita…" className="w-full bg-transparent py-4 text-[15px] outline-none placeholder:text-nevoa" />
        <kbd className="rounded-md border border-white/10 px-1.5 py-0.5 text-[10px] text-nevoa">Esc</kbd></div>
      <div ref={listaRef} className="max-h-[52vh] overflow-y-auto p-2">
        {itens.map((i, n) => {
          const cab = i.grupo !== grupoAnterior; grupoAnterior = i.grupo
          return <div key={i.id}>{cab && <div className="px-3 pb-1 pt-2 text-[10px] uppercase tracking-wider text-nevoa/70">{i.grupo}</div>}
            <button data-i={n} onMouseMove={() => setSel(n)} onClick={i.ir} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left ${n === sel ? 'bg-white/10' : ''}`}>
              <span className={n === sel ? 'text-laranja' : 'text-nevoa'}><Icone nome={i.icone} /></span>
              <span className="min-w-0 flex-1"><span className="block truncate text-sm">{i.rotulo}</span>{i.sub && <span className="block truncate text-[11px] text-nevoa">{i.sub}</span>}</span>
              {n === sel && <span className="text-[11px] text-nevoa">↵</span>}
            </button></div>
        })}
        {!itens.length && <div className="px-3 py-6 text-center text-sm text-nevoa">Nada com “{q}”.</div>}
      </div>
      <div className="flex gap-4 border-t border-white/5 px-4 py-2 text-[11px] text-nevoa"><span>↑↓ navegar</span><span>↵ abrir</span><span className="ml-auto">Ctrl K</span></div>
    </div>
  </div>
}
