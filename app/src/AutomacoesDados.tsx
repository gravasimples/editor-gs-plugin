import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type AutomacoesDados as D } from './api'

// Automações 3, 5, 6 e 7 (03/11/2026): pós-mortem automático, variação do vencedor, alertas e melhor horário. A chave de cada uma fica na lista "Editor GS" abaixo.
const AUTOS: [string, string, string][] = [
  ['posmortem', 'Pós-mortem D+7 automático', 'Ficha factual das peças publicadas há 7+ dias (uma vez por dia).'],
  ['variacao_vencedor', 'Variação do vencedor', 'Peça que fechou o D+7 acima de 1,5× a mediana vira um pedido com 2 variações (outro ângulo, outro formato). Até 2 por semana.'],
  ['alertas', 'Alertas de tração e risco', 'Push quando um post recente foge da mediana ou acumula comentários de problema.'],
  ['melhor_horario', 'Melhor horário por rede', 'Dia × faixa do dia dos seus posts, pela mediana da razão. Recalcula toda semana.'],
]
const ROT_ALERTA = { tracao: 'tração', queda: 'abaixo', risco: 'comentários' } as const

export function AutomacoesDados({ onMudou }: { onMudou?: () => void }) {
  const [d, setD] = useState<D | null>(null); const [ocupado, setOcupado] = useState(''); const [aviso, setAviso] = useState('')
  const carregar = () => api.automacoesDados().then(setD).catch(e => setAviso(e.message))
  useEffect(() => { carregar() }, [])
  async function rodar(id: string, nome: string) {
    if (id === 'variacao_vencedor' && !confirm('Abrir agora um pedido de variação para a peça vencedora mais recente (se houver)? Nada é publicado.')) return
    setOcupado(id); setAviso('')
    try {
      const r = await api.automacaoDadosRodar(id); const x = r[id] || {}
      setAviso(id === 'posmortem' ? `${nome}: ${x.gerados ?? 0} ficha(s) nova(s).` : id === 'variacao_vencedor' ? (x.pedidos?.length ? `Pedido ${x.pedidos.join(', ')} aberto.` : 'Nenhuma peça com pós-mortem acima de 1,5× ainda (ou teto da semana).') : id === 'alertas' ? `${x.novos ?? 0} alerta(s) novo(s).` : 'Melhor horário recalculado.')
      carregar(); onMudou?.()
    } catch (e: any) { setAviso(e.message) } finally { setOcupado('') }
  }
  if (!d) return null
  const ultima: Record<string, string | null | undefined> = { posmortem: d.posmortem?.quando, alertas: d.alertas_quando, melhor_horario: d.melhor_horario?.calculado_em, variacao_vencedor: Object.values(d.variacoes).map(v => v.quando).sort().pop() }
  return <div className="cartao p-3 mt-4">
    <div className="font-bold">Pós-mortem, variações, alertas e horário</div>
    <div className="text-xs text-nevoa">Sem modelo de linguagem, pelos números do GSI (só leitura). Ligue cada uma na lista "Editor GS" abaixo; "Rodar agora" funciona mesmo desligada.</div>
    <div className="mt-2 grid gap-1.5">{AUTOS.map(([id, nome, desc]) => <div key={id} className="flex flex-wrap items-center gap-2 text-xs rounded-xl bg-black/20 px-3 py-2">
      <span className={`inline-block w-2 h-2 rounded-full ${d.ligadas[id] ? 'bg-green-400' : 'bg-white/20'}`} /><span className="font-bold text-sm">{nome}</span><span className="text-nevoa flex-1 min-w-[14rem]">{desc}</span>
      {ultima[id] && <span className="text-nevoa">última: {String(ultima[id]).replace('T', ' ').slice(0, 16)}</span>}
      <button onClick={() => rodar(id, nome)} disabled={!!ocupado} className="rounded-full border border-laranja/60 text-laranja px-3 py-1 hover:bg-laranja/10 disabled:opacity-40">{ocupado === id ? '…' : 'Rodar agora'}</button>
    </div>)}</div>
    {aviso && <div className="text-xs text-green-300 mt-2">{aviso}</div>}

    {d.melhor_horario && <div className="mt-4"><div className="text-[11px] uppercase tracking-wide text-nevoa">Melhor horário (últimos {d.melhor_horario.janela_dias} dias, horário de Brasília)</div>
      <div className="grid sm:grid-cols-2 gap-2 mt-1">{Object.entries(d.melhor_horario.redes).map(([rede, r]) => <div key={rede} className="rounded-xl bg-black/20 p-3 text-xs">
        <div className="font-bold text-sm capitalize">{rede} <span className="font-normal text-nevoa">· {r.posts} posts</span></div>
        {r.melhores.length ? r.melhores.map((f, i) => <div key={i} className="flex gap-2 mt-1"><span className="text-green-300 font-mono w-12">{f.mediana.toFixed(2)}×</span><span>{f.dia} · {f.faixa}</span><span className="text-nevoa ml-auto">{f.n} posts</span></div>) : <div className="text-nevoa mt-1">Poucos posts por faixa ainda.</div>}
        {r.piores.length > 0 && <div className="text-nevoa mt-2">evitar: {r.piores.map(f => `${f.dia} ${f.faixa} (${f.mediana.toFixed(2)}×)`).join(' · ')}</div>}
        <div className="text-[11px] text-nevoa mt-1">{r.nota}</div>
      </div>)}</div></div>}

    <div className="mt-4"><div className="text-[11px] uppercase tracking-wide text-nevoa">Alertas recentes</div>
      {d.alertas.length === 0 ? <div className="text-xs text-nevoa mt-1">Nenhum alerta. Eles saem quando um post dos últimos 14 dias passa de {d.config.alertas?.tracao}× ou cai abaixo de {d.config.alertas?.queda}× a mediana, ou junta {d.config.alertas?.negativos_min}+ comentários de problema. Hoje a coleta do Instagram está parada até a Meta entrar.</div>
        : <div className="grid gap-1 mt-1">{d.alertas.slice(0, 12).map(a => <div key={a.chave} className="flex flex-wrap gap-2 text-xs">
          <span className={`rounded-full px-2 py-0.5 ${a.tipo === 'tracao' ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}`}>{ROT_ALERTA[a.tipo]}</span>
          <a href={a.url} target="_blank" className="truncate flex-1 hover:underline">{a.titulo}</a><span className="text-nevoa">{a.plataforma}{a.razao != null ? ` · ${a.razao}×` : ''}{a.negativos ? ` · ${a.negativos} comentários` : ''}</span></div>)}</div>}</div>

    {Object.keys(d.variacoes).length > 0 && <div className="mt-4"><div className="text-[11px] uppercase tracking-wide text-nevoa">Variações</div>
      <div className="grid gap-1 mt-1">{Object.entries(d.variacoes).map(([slug, v]) => <div key={slug} className="flex flex-wrap gap-2 text-xs"><Link to={`/pecas/${slug}`} className="truncate flex-1 hover:underline">{slug}</Link>
        <span className="text-nevoa">{v.razao ? `${v.razao}× · ` : ''}{v.estado === 'pedido' ? 'pedido aberto' : 'sem material'}</span>{v.conversa && <Link to={`/c/${v.conversa}`} className="text-laranja hover:underline">{v.codigo || 'abrir'}</Link>}</div>)}</div></div>}
  </div>
}
