import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Gancho, type Ganchos as GanchosT } from '../api'

const n = (x: number | null | undefined) => (x == null ? '—' : x.toLocaleString('pt-BR'))
const ORIGENS: [string, string][] = [['tudo', 'Tudo'], ['youtube', 'YouTube (títulos)'], ['instagram', 'Instagram (1ª linha)'], ['app', 'Peças do app'], ['experimento', 'Experimentos']]

export default function Ganchos() {
  const nav = useNavigate()
  const [d, setD] = useState<GanchosT | null>(null); const [erro, setErro] = useState('')
  const [tipo, setTipo] = useState(''); const [aviso, setAviso] = useState(''); const [rodando, setRodando] = useState(''); const [origem, setOrigem] = useState('tudo'); const [medidos, setMedidos] = useState(true); const [q, setQ] = useState(''); const [minimo, setMinimo] = useState('0'); const [copiado, setCopiado] = useState('')
  const carregar = () => api.ganchos({ origem, medidos: medidos ? 'sim' : '', q, minimo, tipo }).then(setD).catch(e => setErro(e.message))
  useEffect(() => { carregar() }, [origem, medidos, minimo, tipo])
  const cor = (r: number | null) => r == null ? 'text-nevoa' : r >= 1.5 ? 'text-green-300' : r <= 0.6 ? 'text-red-300' : ''
  function usar(g: Gancho) { nav('/?text=' + encodeURIComponent(g.pedido)) }
  async function reciclar(g: Gancho) {
    if (!confirm(`Abrir um Reel reciclado usando este gancho como base?\n\n"${g.gancho}"\n\nO app escolhe um evergreen seu acima da mediana, baixa o original e pede gancho, capa e legenda novos a partir deste. Fica só como rascunho: nada é publicado.`)) return
    setRodando(g.gancho); setErro(''); setAviso('')
    try { const r = await api.recicladoRodar(g.gancho); setAviso(r.estado === 'sem_fonte' ? 'Nenhum evergreen disponível com os critérios atuais.' : r.estado === 'sem_video_origem' ? 'Não consegui baixar o original; veja Métricas › Automações.' : `Pedido ${r.codigo || ''} aberto no Editor com este gancho (${r.fonte?.titulo || ''}).`) } catch (e: any) { setErro(e.message) } finally { setRodando('') }
  }
  const ROT: Record<string, string> = Object.fromEntries((d?.tipos || []).map(t => [t.tipo, t.rotulo]))
  async function copiar(g: Gancho) { try { await navigator.clipboard.writeText(g.gancho); setCopiado(g.gancho); setTimeout(() => setCopiado(''), 1500) } catch { /* sem clipboard */ } }
  return <div className="max-w-5xl mx-auto px-4 py-8">
    <h2 className="text-2xl">Ganchos com desempenho</h2>
    <p className="text-nevoa mt-2 text-sm">Todo gancho que a Grava Simples já usou, com a razão sobre a mediana do formato quando o GSI mediu: títulos do YouTube, primeira linha das legendas do Instagram, etiqueta gancho das peças feitas aqui e os experimentos "mesma peça, outro gancho". "Usar" abre o Novo pedido com o gancho como referência (adaptar, não copiar). Números do GSI, não claims.</p>
    <div className="flex flex-wrap gap-2 mt-5 items-center text-sm">
      <select value={origem} onChange={e => setOrigem(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1.5">{ORIGENS.map(([v, r]) => <option key={v} value={v}>{r}</option>)}</select>
      <label className="flex items-center gap-1 text-nevoa"><input type="checkbox" checked={medidos} onChange={e => setMedidos(e.target.checked)} /> só com métrica</label>
      <span className="text-nevoa">razão mínima</span><select value={minimo} onChange={e => setMinimo(e.target.value)} className="rounded-full border border-white/15 bg-card px-2 py-1.5">{['0', '1', '1.5', '2', '3', '5', '10'].map(x => <option key={x} value={x}>{x}×</option>)}</select>
      <form onSubmit={e => { e.preventDefault(); carregar() }} className="flex gap-2 flex-1 min-w-[14rem]"><input value={q} onChange={e => setQ(e.target.value)} placeholder="filtrar por palavra" className="flex-1 rounded-full border border-white/15 bg-card px-3 py-1.5" /><button className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5">filtrar</button></form>
    </div>
    {erro && <div className="text-red-300 text-sm mt-3">{erro}</div>}
    {aviso && <div className="text-green-300 text-sm mt-3">{aviso}</div>}
    {d && d.tipos?.length > 0 && <div className="mt-5">
      <div className="text-sm font-bold">Por tipo de gancho <span className="font-normal text-nevoa text-xs">mediana da razão (a média distorce com um viral); clique para filtrar</span></div>
      <div className="mt-2 grid gap-2 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
        {d.tipos.map(t => <button key={t.tipo} onClick={() => setTipo(tipo === t.tipo ? '' : t.tipo)} className={`cartao p-3 text-left text-xs border ${tipo === t.tipo ? 'border-laranja' : 'border-transparent hover:border-white/15'}`}>
          <div className="flex items-baseline gap-2"><span className="font-bold text-sm text-white">{t.rotulo}</span><span className={`ml-auto font-mono text-base ${cor(t.razao_mediana)}`}>{t.razao_mediana != null ? `${t.razao_mediana.toFixed(2)}×` : '—'}</span></div>
          <div className="text-nevoa mt-0.5">{t.n} ganchos · {t.medidos} medidos{t.pouca_amostra ? ' · pouca amostra' : ''}</div>
          {t.melhor && <div className="mt-1 line-clamp-2 text-white/80">melhor: “{t.melhor}” <span className="text-nevoa">{t.melhor_razao?.toFixed(1)}×</span></div>}
        </button>)}
      </div>
      {tipo && <button onClick={() => setTipo('')} className="mt-2 text-xs text-laranja hover:underline">mostrar todos os tipos</button>}
    </div>}
    {d && <div className="text-xs text-nevoa mt-2">{d.resumo.total} ganchos · {d.resumo.medidos} com métrica · <span className="text-green-300">{d.resumo.acima} acima de 1,5×</span> · <span className="text-red-300">{d.resumo.abaixo} abaixo de 0,6×</span> · YouTube {d.resumo.por_origem.youtube} · Instagram {d.resumo.por_origem.instagram} · app {d.resumo.por_origem.app} · experimentos {d.resumo.por_origem.experimento}</div>}
    {d && <div className="mt-4 grid gap-1 text-sm">
      {d.itens.length === 0 && <div className="text-nevoa">Nenhum gancho com esses filtros.</div>}
      {d.itens.map((g, i) => <div key={`${g.origem}-${g.slug || g.url || i}-${i}`} className="cartao px-3 py-2 flex flex-wrap items-center gap-2">
        <span className={`w-16 text-right font-mono shrink-0 ${cor(g.razao)}`}>{g.razao != null ? `${g.razao.toFixed(1)}×` : '—'}</span>
        <span className="flex-1 min-w-[14rem]"><span className="font-medium">{g.gancho}</span>{g.tipo && <span className="ml-2 rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-nevoa">{ROT[g.tipo] || g.tipo}</span>}{g.papel && <span className="selo ml-2">{g.papel}</span>}</span>
        <span className="text-xs text-nevoa">{g.origem === 'app' ? 'peça' : g.origem}{g.formato ? ` · ${g.formato}` : ''} · {g.data || '?'}{g.views != null ? ` · ${n(g.views)} views` : ''}</span>
        {g.url ? <a href={g.url} target="_blank" className="text-xs text-nevoa hover:underline">abrir ↗</a> : g.slug ? <Link to={`/pecas/${g.slug}`} className="text-xs text-nevoa hover:underline">{g.codigo || 'ficha'}</Link> : null}
        <button onClick={() => copiar(g)} className="rounded-full border border-white/15 px-2 py-0.5 text-xs hover:bg-white/5">{copiado === g.gancho ? 'copiado' : 'copiar'}</button>
        <button onClick={() => usar(g)} className="rounded-full border border-laranja/60 text-laranja px-3 py-0.5 text-xs hover:bg-laranja/10">usar este gancho</button>
        <button onClick={() => reciclar(g)} disabled={!!rodando} title="Abre um Reel reciclado (evergreen seu) com este gancho como base" className="rounded-full border border-white/15 px-3 py-0.5 text-xs hover:bg-white/5 disabled:opacity-40">{rodando === g.gancho ? 'abrindo…' : '♻ no Reel reciclado'}</button>
      </div>)}
    </div>}
    {d && <p className="text-nevoa text-[11px] mt-3">{d.nota}</p>}
  </div>
}
