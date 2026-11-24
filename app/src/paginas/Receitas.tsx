import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ErroCarga, Esqueleto, Vazio } from '../Estados'
import { api, type EstiloBib, type Receita, type ReceitaResumo, type Receitas as ReceitasT } from '../api'

// Estilos › Receitas (16/11/2026): a biblioteca de edição que vem com o código (biblioteca-edicao/). Cada receita é um jeito profissional de editar
// um tipo de vídeo, com prompt pronto; o agente aplica pelo id. Propostas destiladas das referências esperam a decisão do Raphael aqui.
const FORMATO: Record<string, string> = { fala_tela: 'Fala + tela', fala: 'Fala', anuncio: 'Anúncio', aula: 'Aula', animacao: 'Animação', react: 'React', carrossel_video: 'Carrossel em vídeo' }
const ENERGIA: Record<string, { rotulo: string; barras: number; cor: string }> = {
  calmo: { rotulo: 'Calmo', barras: 1, cor: '#6f8cff' }, dinamico: { rotulo: 'Dinâmico', barras: 2, cor: '#F79615' }, bem_dinamico: { rotulo: 'Bem dinâmico', barras: 3, cor: '#ff6a3d' } }
const GRAF: Record<string, string> = { kicker: 'rótulo', manchete: 'manchete', pilula: 'pílula', riscado: 'riscado', checklist: 'checklist', pilulas: 'pílulas', fluxo: 'fluxo',
  cartoes: 'cartões', numero: 'número', logos: 'logos', ondas: 'ondas', recorte: 'recorte', cta: 'CTA' }
const TRANS_COR: Record<string, string> = { seco: '#A7ACBD', punch: '#F79615', deslize: '#284CB8', zoom_blur: '#8b5cf6', flash: '#ffffff', tremor: '#ef4444', luz: '#fde68a', giro: '#22c55e' }

function Energia({ e, mini }: { e: string; mini?: boolean }) {
  const x = ENERGIA[e] || ENERGIA.dinamico
  return <span className="inline-flex items-center gap-1.5" title={`Energia: ${x.rotulo}`}>
    <span className="flex items-end gap-[2px]">{[1, 2, 3].map(i => <span key={i} className="w-[3px] rounded-full transition-all" style={{ height: 4 + i * 3, background: i <= x.barras ? x.cor : 'rgba(255,255,255,.15)' }} />)}</span>
    {!mini && <span className="text-[11px] text-nevoa">{x.rotulo}</span>}
  </span>
}

function BarraTransicoes({ t }: { t?: Record<string, number> }) {
  if (!t || !Object.keys(t).length) return null
  const tot = Object.values(t).reduce((a, b) => a + b, 0) || 1
  return <div>
    <div className="flex h-2 overflow-hidden rounded-full">{Object.entries(t).map(([k, v]) => <div key={k} title={`${k} ${Math.round(v / tot * 100)}%`} style={{ width: `${v / tot * 100}%`, background: TRANS_COR[k] || '#888' }} />)}</div>
    <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-nevoa">{Object.entries(t).map(([k, v]) => <span key={k} className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: TRANS_COR[k] || '#888' }} />{k.replace('_', ' ')} {Math.round(v / tot * 100)}%</span>)}</div>
  </div>
}

function Linha({ partes }: { partes: string[] }) {
  // estrutura da receita como linha do tempo: "0–3 s: ..." vira marca de tempo + texto
  return <ol className="relative ml-2 border-l border-white/10">{partes.map((p, i) => {
    const m = p.match(/^([^:]{1,18}):\s*(.*)$/)
    return <li key={i} className="relative mb-3 pl-4 last:mb-0">
      <span className="absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-marinho bg-laranja" />
      {m ? <><span className="mr-2 rounded-full bg-white/5 px-2 py-0.5 font-mono text-[11px] text-laranja">{m[1]}</span><span className="text-sm">{m[2]}</span></> : <span className="text-sm">{p}</span>}
    </li>
  })}</ol>
}

function Cartao({ r, ativo, onAbrir }: { r: ReceitaResumo; ativo: boolean; onAbrir: () => void }) {
  const en = ENERGIA[r.energia] || ENERGIA.dinamico
  return <button onClick={onAbrir} className={`group relative flex flex-col gap-2 overflow-hidden rounded-[20px] border bg-card p-4 text-left transition hover:-translate-y-0.5 hover:border-white/20 hover:shadow-xl hover:shadow-black/30 ${ativo ? 'border-laranja' : 'border-white/5'}`}>
    <span className="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full opacity-20 blur-2xl transition group-hover:opacity-40" style={{ background: en.cor }} />
    <div className="flex items-center gap-2"><Energia e={r.energia} mini />
      <span className="text-[11px] text-nevoa">{r.formatos.map(f => FORMATO[f] || f).join(' · ')}</span>
      {r.origem === 'local' && <span className="ml-auto rounded-full bg-azul/30 px-2 py-0.5 text-[10px] text-[#cfd8ff]">sua</span>}
      {r.versao > 1 && r.origem !== 'local' && <span className="ml-auto text-[10px] text-nevoa">v{r.versao}</span>}
    </div>
    <div className="font-[Unbounded] text-[15px] leading-snug">{r.nome}</div>
    <div className="line-clamp-3 text-xs text-nevoa">{r.resumo}</div>
    <div className="mt-auto flex flex-wrap gap-1 pt-1">{r.grafismos.slice(0, 4).map(g => <span key={g} className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-nevoa">{GRAF[g] || g}</span>)}
      {!r.grafismos.length && <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-nevoa">sem gráficos</span>}</div>
  </button>
}

function Gaveta({ id, estilos, onFechar, onMudou }: { id: string; estilos: EstiloBib[]; onFechar: () => void; onMudou: () => void }) {
  const nav = useNavigate()
  const [r, setR] = useState<Receita | null>(null); const [erro, setErro] = useState(''); const [copiado, setCopiado] = useState(false); const [ocupado, setOcupado] = useState(false)
  useEffect(() => { setR(null); api.receita(id).then(setR).catch(e => setErro(e.message)) }, [id])
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onFechar() }; window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k) }, [onFechar])
  const base = estilos.find(s => s.nome === r?.base_estilo)
  const medido = r?.medido_nas_referencias ? Object.entries(r.medido_nas_referencias)[0] : null
  const copiar = async () => { if (!r) return; try { await navigator.clipboard.writeText(r.prompt); setCopiado(true); setTimeout(() => setCopiado(false), 1500) } catch {} }
  const usar = () => r && nav('/', { state: { receita: r.id, estilo: r.base_estilo } })
  const decidir = async (aprovar: boolean) => {
    if (!r) return; let motivo = ''
    if (!aprovar) { const m = prompt('Por que recusar? (opcional, ajuda as próximas propostas)'); if (m === null) return; motivo = m }
    setOcupado(true)
    try { aprovar ? await api.receitaAprovar(r.id) : await api.receitaRecusar(r.id, motivo); onMudou(); onFechar() } catch (e: any) { setErro(e.message) } finally { setOcupado(false) }
  }
  const tile = (rot: string, v: any, un = '') => v == null ? null : <div className="rounded-2xl bg-black/25 p-3"><div className="font-[Unbounded] text-lg leading-none">{typeof v === 'number' ? v.toLocaleString('pt-BR') : v}<span className="text-xs text-nevoa">{un}</span></div><div className="mt-1 text-[11px] text-nevoa">{rot}</div></div>
  return <div className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px]" onClick={onFechar}>
    <aside onClick={e => e.stopPropagation()} className="absolute inset-y-0 right-0 flex w-full max-w-xl flex-col overflow-y-auto border-l border-white/10 bg-[#071030] shadow-2xl animate-[gs-entra_.18s_ease-out]">
      {!r ? <div className="p-6 text-sm text-nevoa">{erro || 'Carregando…'}</div> : <>
        <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-white/5 bg-[#071030]/95 px-5 py-3 backdrop-blur">
          <Energia e={r.energia} /><span className="text-[11px] text-nevoa">· {r.formatos.map(f => FORMATO[f] || f).join(' · ')}</span>
          <button onClick={onFechar} className="ml-auto rounded-full px-2 py-1 text-nevoa hover:bg-white/5 hover:text-white" title="Fechar (Esc)">✕</button>
        </div>
        <div className="flex flex-col gap-5 p-5">
          <div>
            {r.origem === 'proposta' && <div className="mb-2 inline-block rounded-full bg-laranja/15 px-2.5 py-0.5 text-[11px] text-laranja">Proposta {r.proposta?.substitui ? 'de versão nova' : 'de receita nova'} · {r.proposta?.referencias?.length || 0} referências</div>}
            <h3 className="text-2xl leading-tight">{r.nome}</h3>
            <p className="mt-1 text-sm text-nevoa">{r.resumo}</p>
          </div>
          <div className="grid grid-cols-[120px_1fr] gap-4">
            <div className="aspect-[9/16] overflow-hidden rounded-2xl bg-black/40">{base?.previa.estado === 'pronta' && base.previa.url
              ? <video src={base.previa.url} poster={base.previa.poster || undefined} muted loop autoPlay playsInline className="h-full w-full object-cover" />
              : <div className="flex h-full items-center justify-center p-2 text-center text-[11px] text-nevoa">prévia do estilo base em Estilos prontos</div>}</div>
            <div className="flex flex-col gap-2 text-xs">
              <div><span className="text-nevoa">Estilo base</span> <code className="rounded bg-white/5 px-1.5">{r.base_estilo}</code></div>
              {r.legenda && <div><span className="text-nevoa">Legenda</span> <code className="rounded bg-white/5 px-1.5">{r.legenda}</code></div>}
              <div><span className="text-nevoa">Gráficos</span> {r.grafismos?.tipos?.length ? <>{r.grafismos.tipos.map(g => GRAF[g] || g).join(', ')}{r.grafismos.a_cada_s ? <span className="text-nevoa"> · até 1 a cada {r.grafismos.a_cada_s} s</span> : null}</> : 'nenhum'}</div>
              {r.grafismos?.visual?.length ? <div><span className="text-nevoa">Acabamento</span> {r.grafismos.visual.join(', ')}</div> : null}
              <div className="mt-1"><div className="mb-1 text-nevoa">Transições</div><BarraTransicoes t={r.transicoes} /></div>
            </div>
          </div>
          {medido && <div><div className="mb-2 text-xs uppercase tracking-wider text-nevoa">Medido em {medido[1].referencias} referências de {FORMATO[medido[0]] || medido[0]}</div>
            <div className="grid grid-cols-3 gap-2">{tile('maior pausa', medido[1].alvos?.pausa_max_s, ' s')}{tile('palavras por segundo', medido[1].alvos?.palavras_por_s)}{tile('um gráfico a cada', medido[1].padroes?.grafismo_a_cada_s, ' s')}</div></div>}
          <section><div className="mb-2 text-xs uppercase tracking-wider text-nevoa">Estrutura</div><Linha partes={r.estrutura} /></section>
          <section className="grid gap-3 sm:grid-cols-2">
            <div><div className="mb-2 text-xs uppercase tracking-wider text-nevoa">Regras</div><ul className="grid gap-1.5 text-sm">{r.regras.map((x, i) => <li key={i} className="flex gap-2"><span className="text-laranja">✓</span>{x}</li>)}</ul></div>
            <div><div className="mb-2 text-xs uppercase tracking-wider text-nevoa">Evitar</div><ul className="grid gap-1.5 text-sm">{r.evitar.map((x, i) => <li key={i} className="flex gap-2"><span className="text-red-300">✕</span>{x}</li>)}</ul></div>
          </section>
          <section><div className="mb-2 flex items-center text-xs uppercase tracking-wider text-nevoa">Prompt pronto<button onClick={copiar} className="ml-auto rounded-full border border-white/15 px-2.5 py-0.5 normal-case tracking-normal hover:bg-white/5">{copiado ? 'Copiado ✓' : 'Copiar'}</button></div>
            <p className="rounded-2xl border border-white/5 bg-black/25 p-3 text-sm leading-relaxed">{r.prompt}</p></section>
          {erro && <div className="text-sm text-red-300">{erro}</div>}
        </div>
        <div className="sticky bottom-0 mt-auto flex gap-2 border-t border-white/5 bg-[#071030]/95 px-5 py-3 backdrop-blur">
          {r.origem === 'proposta'
            ? <><button disabled={ocupado} onClick={() => decidir(true)} className="btn-laranja px-5 py-2 text-sm">Aprovar na biblioteca</button><button disabled={ocupado} onClick={() => decidir(false)} className="rounded-full border border-white/15 px-4 py-2 text-sm hover:bg-white/5">Recusar</button></>
            : <><button onClick={usar} className="btn-laranja px-5 py-2 text-sm">Usar no pedido</button><button onClick={() => nav('/', { state: { receita: r.id, estilo: r.base_estilo, pedido: r.prompt } })} className="rounded-full border border-white/15 px-4 py-2 text-sm hover:bg-white/5">Pedir com este prompt</button></>}
        </div>
      </>}
    </aside>
  </div>
}

export default function Receitas({ estilos }: { estilos: EstiloBib[] }) {
  const nav = useNavigate()
  const [d, setD] = useState<ReceitasT | null>(null); const [props, setProps] = useState<Receita[]>([]); const [erro, setErro] = useState('')
  const [formato, setFormato] = useState(''); const [energia, setEnergia] = useState(''); const [busca, setBusca] = useState(''); const [aberta, setAberta] = useState('')
  const [destilando, setDestilando] = useState(false)
  const carregar = () => { api.receitas().then(setD).catch(e => setErro(e.message)); api.receitasPropostas().then(r => setProps(r.propostas)).catch(() => {}) }
  useEffect(() => { carregar() }, [])
  // link do Início (/estilos?aba=receitas#propostas): a rota é carregada sob demanda, então rola quando as propostas chegam
  const loc = useLocation()
  useEffect(() => { if (loc.hash === '#propostas' && props.length) document.getElementById('propostas')?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }, [loc.hash, props.length])
  const lista = useMemo(() => {
    const q = busca.trim().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    return (d?.receitas || []).filter(r => (!formato || r.formatos.includes(formato)) && (!energia || r.energia === energia)
      && (!q || `${r.nome} ${r.resumo} ${r.temas.join(' ')}`.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').includes(q)))
  }, [d, formato, energia, busca])
  const destilar = async () => { setDestilando(true); try { await api.receitasDestilar(); carregar() } catch (e: any) { setErro(e.message) } finally { setDestilando(false) } }
  const pedirPropostas = () => nav('/', { state: { fluxo: 'destilar-estilos', pedido: 'Destile as referências novas do repertório em receitas da biblioteca de edição (fluxo destilar-estilos): até 3 propostas, cada uma com pelo menos 2 referências de apoio.' } })
  const chip = (ativo: boolean) => `rounded-full border px-3 py-1 text-xs transition ${ativo ? 'border-laranja bg-laranja/10 text-laranja' : 'border-white/10 text-nevoa hover:bg-white/5 hover:text-white'}`
  const pend = d?.pendentes
  return <div>
    <div className="relative overflow-hidden rounded-[20px] border border-white/5 bg-gradient-to-br from-card to-[#0a1640] p-5">
      <span className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-laranja/20 blur-3xl" />
      <div className="relative flex flex-wrap items-end gap-4">
        <div className="max-w-xl"><div className="text-xs uppercase tracking-wider text-laranja">Biblioteca de edição</div>
          <h3 className="mt-1 text-xl leading-snug">{d?.n ?? '…'} receitas de edição profissional, prontas para pedir</h3>
          <p className="mt-1 text-sm text-nevoa">Cada receita diz ao Editor o ritmo, os gráficos, as transições e a estrutura de um tipo de vídeo. Vem com o projeto: quem instala o Editor GS recebe todas.</p></div>
        <div className="ml-auto flex flex-wrap gap-2 text-xs">
          {pend && <div className="rounded-2xl bg-black/25 px-3 py-2"><b className="text-white">{pend.decupadas}</b> <span className="text-nevoa">referências estudadas</span>{pend.novas > 0 && <> · <b className="text-laranja">{pend.novas}</b> <span className="text-nevoa">ainda sem receita</span></>}</div>}
        </div>
      </div>
      {pend && pend.novas > 0 && <div className="relative mt-4 flex flex-wrap items-center gap-2 text-xs">
        <button onClick={pedirPropostas} className="btn-laranja px-4 py-1.5">Pedir propostas ao Editor</button>
        <button onClick={destilar} disabled={destilando} title="Atualiza os padrões medidos (não gasta modelo)" className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5">{destilando ? 'Atualizando…' : 'Atualizar padrões medidos'}</button>
        <span className="text-nevoa">O Editor lê as referências novas e propõe receitas; você aprova aqui.</span>
      </div>}
    </div>

    {props.length > 0 && <div id="propostas" className="mt-5 scroll-mt-4"><div className="mb-2 flex items-center gap-2"><h3 className="text-lg">Propostas para aprovar</h3><span className="rounded-full bg-laranja px-2 text-[11px] font-bold text-marinho">{props.length}</span></div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{props.map(p => <button key={p.id} onClick={() => setAberta(p.id)} className="flex flex-col rounded-[20px] border border-dashed border-laranja/50 bg-laranja/5 p-4 text-left hover:bg-laranja/10">
        <div className="text-[11px] text-laranja">{p.proposta?.substitui ? 'versão nova de uma receita' : 'receita nova'} · {p.proposta?.referencias?.length || 0} referências</div>
        <div className="mt-1 font-[Unbounded] text-[15px]">{p.nome}</div><div className="mt-1 line-clamp-2 text-xs text-nevoa">{p.resumo}</div></button>)}</div></div>}

    <div className="mt-5 flex flex-wrap items-center gap-1.5">
      <input value={busca} onChange={e => setBusca(e.target.value)} placeholder="Buscar receita (ex.: depoimento, lista, calmo)" className="mr-2 w-full rounded-full bg-black/30 px-4 py-1.5 text-sm outline-none placeholder:text-nevoa sm:w-72" />
      <button onClick={() => setFormato('')} className={chip(!formato)}>Todos</button>
      {Object.keys(FORMATO).filter(f => d?.receitas.some(r => r.formatos.includes(f))).map(f => <button key={f} onClick={() => setFormato(formato === f ? '' : f)} className={chip(formato === f)}>{FORMATO[f]}</button>)}
      <span className="mx-1 h-4 w-px bg-white/10" />
      {Object.entries(ENERGIA).map(([k, v]) => <button key={k} onClick={() => setEnergia(energia === k ? '' : k)} className={`${chip(energia === k)} inline-flex items-center gap-1.5`}><Energia e={k} mini />{v.rotulo}</button>)}
    </div>
    {erro && d && <div className="mt-3 text-sm text-red-300">{erro}</div>}
    {erro && !d ? <ErroCarga erro={erro} onTentar={carregar} className="mt-4" /> : !d ? <Esqueleto className="mt-4" n={8} /> : lista.length
      ? <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{lista.map(r => <Cartao key={r.id} r={r} ativo={aberta === r.id} onAbrir={() => setAberta(r.id)} />)}</div>
      : <Vazio className="mt-4" icone="receitas" titulo={d.receitas.length ? 'Nenhuma receita com esse filtro' : 'Nenhuma receita ainda'} texto={d.receitas.length ? 'Tente outro formato, outra energia ou limpe a busca.' : 'A biblioteca de edição vem com o projeto; peça propostas ao Editor a partir das referências.'} acao={d.receitas.length ? { rotulo: 'Limpar filtros', onClick: () => { setFormato(''); setEnergia(''); setBusca('') } } : undefined} />}
    {aberta && <Gaveta id={aberta} estilos={estilos} onFechar={() => setAberta('')} onMudou={carregar} />}
  </div>
}
