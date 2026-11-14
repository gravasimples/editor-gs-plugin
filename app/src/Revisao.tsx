import type { Revisao } from './api'

/** Avisos do revisor de marca (regras duras do manual). Só aponta; a decisão é humana. */
export function AvisosMarca({ r, compacto = false }: { r: Revisao | null | undefined; compacto?: boolean }) {
  if (!r) return null
  if (r.ok && r.avisos.length === 0) return <span className="rounded-full bg-green-500/20 text-green-300 px-2 py-0.5 text-[11px]">marca ok</span>
  const cor = (g: string) => g === 'alta' ? 'bg-red-500/20 text-red-300' : g === 'media' ? 'bg-laranja/20 text-laranja' : 'bg-white/10 text-nevoa'
  if (compacto) return <span className="inline-flex gap-1">{(['alta', 'media', 'baixa'] as const).filter(g => r.resumo[g]).map(g => <span key={g} className={`rounded-full px-2 py-0.5 text-[11px] ${cor(g)}`}>{r.resumo[g]} {g}</span>)}</span>
  return <div className="grid gap-1 text-xs">{r.avisos.map((a, i) => <div key={i} className="flex gap-2 items-start"><span className={`rounded-full px-2 py-0.5 text-[10px] shrink-0 ${cor(a.gravidade)}`}>{a.gravidade}</span><span><b>{a.campo}</b>: {a.msg} <span className="text-nevoa">“{a.trecho}”</span></span></div>)}</div>
}
