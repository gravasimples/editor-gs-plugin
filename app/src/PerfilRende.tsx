import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type PerfilRende as R } from './api'

// Perfil vivo do Thiago (03/11/2026): o que rende por duração, formato, gancho e horário. O mesmo texto vai para o Editor antes de cada pedido.
const Faixas = ({ t, xs }: { t: string; xs: R['duracao']['reels'] }) => xs.length === 0 ? null : <div className="rounded-xl bg-black/20 p-3 text-xs">
  <div className="font-bold text-sm">{t}</div>
  {xs.map(x => <div key={x.faixa} className="flex items-center gap-2 mt-1"><span className="w-24">{x.faixa}</span>
    <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden"><div className={`h-full ${x.mediana >= 1 ? 'bg-laranja' : 'bg-white/30'}`} style={{ width: `${Math.min(100, x.mediana * 33)}%` }} /></div>
    <span className={`font-mono w-14 text-right ${x.pouca_amostra ? 'text-nevoa' : ''}`}>{x.mediana.toFixed(2)}×</span><span className="text-nevoa w-16 text-right">{x.n} peça{x.n > 1 ? 's' : ''}{x.pouca_amostra ? '*' : ''}</span></div>)}
</div>

export function PerfilRende() {
  const [r, setR] = useState<R | null>(null); const [erro, setErro] = useState(''); const [ocupado, setOcupado] = useState(false)
  const carregar = (atualizar = false) => { setOcupado(true); api.perfilRende(atualizar).then(setR).catch(e => setErro(e.message)).finally(() => setOcupado(false)) }
  useEffect(() => { carregar() }, [])
  if (erro) return <div className="text-red-300 text-sm mt-5">{erro}</div>
  if (!r) return <div className="text-nevoa text-sm mt-5">Calculando…</div>
  if (r.erro) return <div className="text-red-300 text-sm mt-5">{r.erro}</div>
  return <div className="mt-5 text-sm">
    <div className="flex flex-wrap items-center gap-2"><div className="font-bold text-lg">Perfil do Thiago · o que rende</div>
      <span className="text-xs text-nevoa">{r.n_pecas} peças próprias · atualizado {r.gerado_em.replace('T', ' ')} (sozinho, uma vez por dia)</span>
      <button onClick={() => carregar(true)} disabled={ocupado} className="ml-auto rounded-full border border-white/15 px-3 py-1 text-xs hover:bg-white/5 disabled:opacity-40">{ocupado ? '…' : '↻ Atualizar agora'}</button></div>
    <div className="text-xs text-nevoa mt-1">O Editor lê este resumo antes de escrever gancho, escolher duração e montar o pedido. {r.nota}</div>
    {r.avisos.map(a => <div key={a} className="text-xs text-laranja mt-2">⚠ {a}</div>)}
    {r.pistas.length > 0 && <div className="cartao p-3 mt-3"><div className="text-[11px] uppercase tracking-wide text-nevoa">Pistas</div>
      <ul className="mt-1 grid gap-1">{r.pistas.map(p => <li key={p}>• {p}</li>)}</ul></div>}
    <div className="grid sm:grid-cols-3 gap-2 mt-3"><Faixas t="Reels por duração" xs={r.duracao.reels} /><Faixas t="Shorts por duração" xs={r.duracao.shorts} /><Faixas t="YouTube longo por duração" xs={r.duracao.youtube_longo} /></div>
    {r.ganchos.length > 0 && <div className="cartao p-3 mt-3"><div className="flex items-center"><div className="text-[11px] uppercase tracking-wide text-nevoa">Ganchos por tipo (mediana da razão)</div><Link to="/ganchos" className="ml-auto text-xs text-laranja hover:underline">ver ganchos →</Link></div>
      <div className="grid gap-1 mt-1">{r.ganchos.map(g => <div key={g.tipo} className="flex gap-2 text-xs min-w-0"><span className="w-44">{g.rotulo}</span><span className="font-mono w-14">{g.razao_mediana?.toFixed(2)}×</span><span className="text-nevoa w-20">{g.medidos} medidos{g.pouca_amostra ? '*' : ''}</span><span className="text-nevoa truncate flex-1 min-w-0">{g.melhor}</span></div>)}</div></div>}
    <div className="text-[11px] text-nevoa mt-2">* pouca amostra (menos de 5 peças): é pista, não regra. Horário por rede fica em Automações › Melhor horário. Perfil completo (posts, hashtags, comentários) em <Link to="/referencias" className="text-laranja hover:underline">Referências › Perfil do Thiago</Link>.</div>
  </div>
}
