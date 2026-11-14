import { useEffect, useState } from 'react'
import type { ProgressoPedido } from './api'

// Progresso ao vivo do pedido (11/11/2026): etapa atual, barra de 0 a 100% e "cerca de N min" (gateway: servico/progresso.py).
// A estimativa vem das rodadas anteriores; entre um polling e outro o relógio anda aqui no navegador.
const fmt = (s: number) => s < 60 ? `${Math.max(1, Math.round(s))} s` : s < 3600 ? `${Math.round(s / 60)} min` : `${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} min`

export default function Progresso({ p }: { p?: ProgressoPedido | null }) {
  const [tique, setTique] = useState(0)
  useEffect(() => { setTique(0); const t = setInterval(() => setTique(x => x + 1), 1000); return () => clearInterval(t) }, [p?.decorrido_s, p?.atual])
  if (!p) return (
    <div className="mt-3 rounded-2xl bg-card/80 border border-white/5 px-4 py-3">
      <div className="flex items-center gap-2 text-sm"><span className="w-1.5 h-1.5 rounded-full bg-laranja animate-pulse" />Começando: o Editor está lendo o pedido</div>
      <div className="mt-2 h-1.5 rounded-full bg-white/10 overflow-hidden"><div className="h-full w-1/3 rounded-full bg-gradient-to-r from-laranja to-laranja2 animate-[gs-vai_1.6s_ease-in-out_infinite]" /></div>
    </div>
  )
  const decorrido = p.decorrido_s + tique
  const restante = p.restante_s != null ? Math.max(0, p.restante_s - tique) : null
  const idx = p.etapas.findIndex(e => e.estado === 'atual')
  return (
    <div className="mt-3 rounded-2xl bg-card/80 border border-white/5 px-4 py-3" aria-live="polite">
      <div className="flex items-baseline gap-3">
        <span className="text-sm font-semibold flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-laranja animate-pulse" />{p.atual_nome}</span>
        <span className="ml-auto text-xs text-nevoa tabular-nums">
          {p.lenta ? <span className="text-amber-300" title="Esta etapa está levando bem mais que o normal. Se nada mudar, use ■ Parar e ▶ Retomar.">demorando mais que o normal</span>
            : restante != null ? <span title={p.estimativa === 'historico' ? `Estimativa pelas últimas ${p.base_rodadas} edições` : 'Estimativa inicial (ainda há poucas edições medidas)'}>cerca de {fmt(restante)} para terminar</span> : null}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden" role="progressbar" aria-valuenow={p.pct ?? 0} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-full rounded-full bg-gradient-to-r from-laranja to-laranja2 transition-[width] duration-700" style={{ width: `${p.pct ?? 2}%` }} />
        </div>
        <span className="text-xs font-semibold tabular-nums w-9 text-right">{p.pct ?? 0}%</span>
      </div>
      <ol className="mt-3 flex items-start">
        {p.etapas.map((e, i) => (
          <li key={e.id} className="flex-1 flex flex-col items-center min-w-0 relative" title={e.nome}>
            {i > 0 && <span className={`absolute top-[7px] right-1/2 w-full h-px ${i <= idx ? 'bg-laranja/70' : 'bg-white/10'}`} />}
            <span className={`relative z-10 w-[15px] h-[15px] rounded-full flex items-center justify-center text-[9px] leading-none
              ${e.estado === 'feita' ? 'bg-laranja text-marinho' : e.estado === 'atual' ? 'bg-marinho border-2 border-laranja shadow-[0_0_0_4px_rgba(247,150,21,.15)]' : 'bg-card2 border border-white/15'}`}>
              {e.estado === 'feita' ? '✓' : ''}</span>
            <span className={`mt-1.5 text-[10px] leading-tight text-center px-0.5 hidden sm:block ${e.estado === 'atual' ? 'text-white' : e.estado === 'feita' ? 'text-nevoa' : 'text-nevoa/50'}`}>{e.nome}</span>
          </li>
        ))}
      </ol>
      <div className="mt-2 text-[11px] text-nevoa/80 tabular-nums">trabalhando há {fmt(decorrido)}{p.na_etapa_s > 90 ? ` · nesta etapa há ${fmt(p.na_etapa_s + tique)}` : ''}</div>
    </div>
  )
}
