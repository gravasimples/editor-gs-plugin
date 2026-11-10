import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type BibliotecaEstilos, type ElementoBib, type EstiloBib, type LegendaModelo, type Previa } from '../api'

// Página Estilos (03/11/2026): biblioteca visual no jeito do Máquina — estilos prontos, legendas, animações, transições, elementos e formatos,
// cada um com prévia feita pelo mesmo motor da entrega; "Montar meu estilo" junta as peças. Os .json que o agente lê ficam na pasta do fim.
// As conexões do Canva e do YouTube que ficavam aqui foram para a página Redes.
const CORES: [string, string][] = [['#F79615', 'laranja (marca)'], ['#E9760D', 'laranja escuro'], ['#FFD400', 'amarelo'], ['#22C55E', 'verde'], ['#38BDF8', 'azul claro'], ['#F472B6', 'rosa'], ['#A78BFA', 'roxo'], ['#FFFFFF', 'branco']]
type Aba = 'estilos' | 'legendas' | 'animacao' | 'transicao' | 'elemento' | 'formato'
const ABAS: [Aba, string][] = [['estilos', 'Estilos prontos'], ['legendas', 'Legendas'], ['animacao', 'Animações'], ['transicao', 'Transições'], ['elemento', 'Elementos'], ['formato', 'Formatos']]
const NIVEL: Record<number, string> = { 1: '1 limpo', 2: '2 dinâmico', 3: '3 profissional' }
const PRO = ['palavras-chave', 'ritmo-4s', 'barra-progresso', 'sfx', 'broll-janela', 'broll-cheio', 'gancho-palavra', 'capitulos', 'capitulos-auto']
type Montagem = { nome: string; descricao: string; legenda: string; cor_destaque: string; elementos: string[]; transicao: string; formato: string; trilha: boolean; temas: string[] }
const VAZIO: Montagem = { nome: '', descricao: '', legenda: 'karaoke-pop', cor_destaque: '#F79615', elementos: [], transicao: '', formato: '', trilha: false, temas: [] }

function PreviaVideo({ previa, pedir, som }: { previa: Previa; pedir: () => void; som?: boolean }) {
  const ref = useRef<HTMLVideoElement>(null); const caixa = useRef<HTMLDivElement>(null); const [visivel, setVisivel] = useState(false)
  useEffect(() => {
    const el = caixa.current; if (!el) return
    const io = new IntersectionObserver(([e]) => setVisivel(e.isIntersecting), { rootMargin: '200px' }); io.observe(el); return () => io.disconnect()
  }, [])
  useEffect(() => { const v = ref.current; if (!v) return; if (visivel) v.play().catch(() => {}); else v.pause() }, [visivel, previa.url])
  return <div ref={caixa} className="relative aspect-[9/16] w-full overflow-hidden rounded-2xl bg-black/50">
    {previa.estado === 'pronta' && previa.url
      ? <video ref={ref} src={visivel ? previa.url : undefined} poster={previa.poster || undefined} muted={!som} loop playsInline preload="none" controls={som} className="h-full w-full object-cover" />
      : <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-3 text-center text-xs text-nevoa">
        {previa.estado === 'fila' && <><span className="animate-pulse text-2xl">⏳</span>Na fila da prévia</>}
        {previa.estado === 'gerando' && <><span className="animate-spin text-2xl">◌</span>Gerando com o motor da entrega…</>}
        {previa.estado === 'erro' && <><span className="text-red-300">A prévia falhou</span><span className="line-clamp-3 opacity-70">{previa.erro}</span><button onClick={pedir} className="rounded-full border border-white/20 px-3 py-1 hover:bg-white/5">Tentar de novo</button></>}
        {previa.estado === 'sem' && <><span className="text-2xl">▶</span><button onClick={pedir} className="rounded-full border border-laranja/60 px-3 py-1 text-laranja hover:bg-laranja/10">Gerar prévia</button></>}
        {previa.estado === 'indisponivel' && <>Sem prévia</>}
      </div>}
  </div>
}

function Temas({ temas, rotulos }: { temas?: string[]; rotulos: Record<string, string> }) {
  if (!temas?.length) return null
  return <div className="flex flex-wrap gap-1">{temas.slice(0, 4).map(t => <span key={t} className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-nevoa">{rotulos[t] || t}</span>)}</div>
}

export default function Estilos() {
  const nav = useNavigate()
  const [bib, setBib] = useState<BibliotecaEstilos | null>(null); const [erro, setErro] = useState('')
  const [aba, setAba] = useState<Aba>('estilos'); const [tema, setTema] = useState('')
  const [montando, setMontando] = useState(false); const [m, setM] = useState<Montagem>(VAZIO); const [salvando, setSalvando] = useState(false)
  const [arquivo, setArquivo] = useState<{ titulo: string; conteudo: any } | null>(null)
  const carregar = () => api.estilosBiblioteca().then(setBib).catch(e => setErro(String(e.message || e)))
  useEffect(() => { carregar() }, [])
  const todos = bib ? [...bib.estilos, ...bib.legendas, ...bib.elementos] : []
  const ocupada = !!bib && (bib.fila > 0 || todos.some(x => x.previa.estado === 'fila' || x.previa.estado === 'gerando'))
  useEffect(() => { if (!ocupada) return; const t = setInterval(carregar, 4000); return () => clearInterval(t) }, [ocupada])
  const rotulos = useMemo(() => Object.fromEntries((bib?.temas || []).map(t => [t.id, t.rotulo])), [bib])
  const filtra = <T extends { temas?: string[] }>(xs: T[]) => (tema ? xs.filter(x => x.temas?.includes(tema)) : xs)
  const pedir = async (itens: string) => { try { await api.pedirPrevias(itens); carregar() } catch (e: any) { setErro(e.message) } }
  const faltando = todos.filter(x => x.previa.estado === 'sem' || x.previa.estado === 'erro').length
  const contagem: Record<Aba, number> = { estilos: bib?.estilos.length || 0, legendas: bib?.legendas.length || 0, animacao: 0, transicao: 0, elemento: 0, formato: 0 }
  bib?.elementos.forEach(e => { contagem[e.categoria]++ })

  const abrirMontagem = (parcial: Partial<Montagem> = {}) => { setM(atual => ({ ...atual, ...parcial, elementos: parcial.elementos ? Array.from(new Set([...atual.elementos, ...parcial.elementos])) : atual.elementos })); setMontando(true) }
  const alterna = (id: string) => setM(x => ({ ...x, elementos: x.elementos.includes(id) ? x.elementos.filter(e => e !== id) : [...x.elementos, id] }))
  async function salvar() {
    setSalvando(true); setErro('')
    try { await api.montarEstilo(m); setMontando(false); setM(VAZIO); setAba('estilos'); setTema(''); carregar() } catch (e: any) { setErro(e.message) } finally { setSalvando(false) }
  }
  async function apagar(n: string) { if (!confirm(`Apagar o estilo ${n}?`)) return; try { await api.apagarEstilo(n); carregar() } catch (e: any) { setErro(e.message) } }
  const usarNoPedido = (nome: string) => nav('/', { state: { estilo: nome } })
  const pedirCom = (texto: string) => nav('/', { state: { pedido: texto } })

  const btn = 'rounded-full border border-white/15 px-3 py-1 hover:bg-white/5'
  const chip = (ativo: boolean) => `rounded-full border px-2.5 py-1 text-xs ${ativo ? 'border-laranja bg-laranja/10 text-laranja' : 'border-white/15 hover:bg-white/5'}`
  const cartao = (chave: string, titulo: string, desc: string, previa: Previa, tipoId: string, extra: React.ReactNode, acoes: React.ReactNode, temas?: string[], som?: boolean) =>
    <div key={chave} className="cartao flex flex-col gap-2 p-3">
      <PreviaVideo previa={previa} pedir={() => pedir(tipoId)} som={som} />
      <div className="flex items-start gap-2"><div className="font-bold leading-tight">{titulo}</div><div className="ml-auto flex shrink-0 gap-1">{extra}</div></div>
      <div className="text-xs text-nevoa">{desc}</div>
      <Temas temas={temas} rotulos={rotulos} />
      <div className="mt-auto flex flex-wrap gap-1.5 pt-1 text-xs">{acoes}</div>
    </div>

  const estiloCard = (s: EstiloBib) => cartao(`e-${s.nome}`, s.nome, s.descricao || '', s.previa, `estilo:${s.nome}`,
    <>{s.montagem?.nivel ? <span className="selo">{NIVEL[s.montagem.nivel] || s.montagem.nivel}</span> : null}</>,
    <><button onClick={() => usarNoPedido(s.nome)} className="btn-laranja px-3 py-1">Usar no pedido</button>
      <button onClick={() => setArquivo({ titulo: `estilos/${s.nome}.json`, conteudo: { legenda: s.legenda, montagem: s.montagem, temas: s.temas, montado: s.montado } })} className={btn}>Ver ajustes</button>
      {!s.casa && <button onClick={() => apagar(s.nome)} className="rounded-full px-2 py-1 text-nevoa hover:text-red-300">Apagar</button>}</>, s.temas)
  const legendaCard = (l: LegendaModelo) => cartao(`l-${l.id}`, l.nome, l.descricao, l.previa, `legenda:${l.id}`,
    <>{l.fora_da_marca && <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-[11px] text-red-200">fora da marca</span>}{m.legenda === l.id && montando && <span className="selo">no meu estilo</span>}</>,
    <><button onClick={() => abrirMontagem({ legenda: l.id })} className="btn-laranja px-3 py-1">Usar no meu estilo</button>
      <button onClick={() => pedirCom(`Use a legenda do modelo \`${l.id}\` (${l.nome}): estilo inline {"base": "padrao", "legenda_modelo": "${l.id}"}.`)} className={btn}>Pedir com ela</button></>, l.temas)
  const elementoCard = (e: ElementoBib) => {
    const naMontagem = e.categoria === 'transicao' ? m.transicao === e.id : e.categoria === 'formato' ? m.formato === e.id : m.elementos.includes(e.id)
    const usar = () => e.categoria === 'transicao' ? abrirMontagem({ transicao: e.id }) : e.categoria === 'formato' ? abrirMontagem({ formato: e.id }) : abrirMontagem({ elementos: [e.id] })
    return cartao(`x-${e.id}`, e.nome, e.descricao, e.previa, `elemento:${e.id}`, <>{naMontagem && <span className="selo">no meu estilo</span>}</>,
      <><button onClick={usar} className="btn-laranja px-3 py-1">{e.categoria === 'transicao' ? 'Usar esta transição' : e.categoria === 'formato' ? 'Usar este formato' : 'Pôr no meu estilo'}</button>
        <button onClick={() => pedirCom(`Edite este vídeo com ${e.como_pedir} (${e.parametro}).`)} className={btn}>Pedir com isso</button></>, e.temas, e.id === 'sfx')
  }

  const grade = 'grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5'
  const vazio = <div className="cartao p-6 text-sm text-nevoa">Nada nesta seção combina com o tema escolhido. Tire o filtro para ver tudo.</div>
  const casa = filtra(bib?.estilos.filter(s => s.casa) || []); const meus = filtra(bib?.estilos.filter(s => !s.casa) || [])
  const doTipo = (c: ElementoBib['categoria']) => filtra(bib?.elementos.filter(e => e.categoria === c) || [])
  const legSel = bib?.legendas.find(l => l.id === m.legenda)
  const nPro = m.elementos.filter(e => PRO.includes(e)).length
  const nivelPrev = nPro >= 4 ? 3 : (nPro >= 1 || m.elementos.includes('zoom-frase') || m.elementos.includes('clarao')) ? 2 : 1

  return <div className="mx-auto max-w-7xl px-4 py-8">
    <div className="flex flex-wrap items-center gap-3">
      <div><h2 className="text-2xl">Estilos</h2><p className="text-sm text-nevoa">Veja cada legenda, animação, transição e elemento rodando num trecho real do Thiago, e monte o jeito de editar de cada tipo de vídeo.</p></div>
      <div className="ml-auto flex flex-wrap gap-2">
        {faltando > 0 && <button onClick={() => pedir('todas')} className={btn}>Gerar as prévias que faltam ({faltando})</button>}
        <button onClick={() => abrirMontagem()} className="btn-laranja px-4 py-2 text-sm">+ Montar meu estilo</button>
      </div>
    </div>
    {ocupada && <div className="mt-3 text-xs text-nevoa">Gerando prévias com os motores da entrega, uma por vez ({bib?.fila} na fila). Pode navegar: elas aparecem sozinhas.</div>}
    {erro && <div className="mt-3 text-sm text-red-300">{erro}</div>}

    <div className="mt-5 flex flex-wrap items-center gap-1.5"><span className="mr-1 text-xs text-nevoa">Para que vídeo?</span>
      <button onClick={() => setTema('')} className={chip(!tema)}>Todos</button>
      {bib?.temas.map(t => <button key={t.id} onClick={() => setTema(tema === t.id ? '' : t.id)} className={chip(tema === t.id)}>{t.rotulo}</button>)}
    </div>

    <div className="sticky top-0 z-10 -mx-4 mt-4 flex gap-1 overflow-x-auto bg-marinho/90 px-4 py-2 backdrop-blur">
      {ABAS.map(([id, r]) => <button key={id} onClick={() => setAba(id)} className={`whitespace-nowrap rounded-full px-4 py-1.5 text-sm ${aba === id ? 'btn-laranja' : 'border border-white/10 hover:bg-white/5'}`}>{r} <span className="opacity-60">{contagem[id]}</span></button>)}
    </div>

    {!bib ? <div className="mt-6 text-nevoa">Carregando…</div> : <div className="mt-4">
      {aba === 'estilos' && <>
        <h3 className="mb-2 text-lg">Meus estilos</h3>
        {meus.length ? <div className={grade}>{meus.map(estiloCard)}</div> : <div className="cartao p-5 text-sm text-nevoa">Ainda não tem estilo seu. Clique em <b>+ Montar meu estilo</b>, escolha uma legenda e os elementos, e ele aparece aqui e no Novo pedido.</div>}
        <h3 className="mb-2 mt-6 text-lg">Da casa</h3>
        {casa.length ? <div className={grade}>{casa.map(estiloCard)}</div> : vazio}
      </>}
      {aba === 'legendas' && (filtra(bib.legendas).length ? <div className={grade}>{filtra(bib.legendas).map(legendaCard)}</div> : vazio)}
      {(['animacao', 'transicao', 'elemento', 'formato'] as const).map(c => aba === c && <div key={c}>
        {c === 'transicao' && <p className="mb-3 text-xs text-nevoa">Transições entram entre cenas nos vídeos com locução e slides. Nos Reels de fala o corte é seco ou com clarão (aba Animações).</p>}
        {c === 'formato' && <p className="mb-3 text-xs text-nevoa">Formatos precisam de dois vídeos (rosto e tela, ou antes e depois). Anexe os dois no pedido.</p>}
        {doTipo(c).length ? <div className={grade}>{doTipo(c).map(elementoCard)}</div> : vazio}
      </div>)}
    </div>}

    <details className="cartao mt-10 p-4">
      <summary className="cursor-pointer font-bold">📁 Pasta do agente <span className="text-sm font-normal text-nevoa">os arquivos que o Editor lê (é daqui que ele tira cada estilo)</span></summary>
      <p className="mt-2 text-xs text-nevoa">Não precisa mexer aqui: a página escreve esses arquivos quando você monta um estilo. Ficam em <code>estilos/</code> (estilos completos), <code>estilos/legendas/</code> (modelos de legenda) e <code>estilos/elementos.json</code> (animações, transições, elementos e formatos). Amostra das prévias: {bib?.amostra}.</p>
      <div className="mt-3 grid gap-1 text-xs sm:grid-cols-2 lg:grid-cols-3">
        {bib?.estilos.map(s => <button key={s.nome} onClick={() => setArquivo({ titulo: `estilos/${s.nome}.json`, conteudo: s })} className="truncate rounded-lg px-2 py-1 text-left hover:bg-white/5">📄 estilos/{s.nome}.json</button>)}
        {bib?.legendas.map(l => <button key={l.id} onClick={() => setArquivo({ titulo: `estilos/legendas/${l.id}.json`, conteudo: l })} className="truncate rounded-lg px-2 py-1 text-left hover:bg-white/5">📄 estilos/legendas/{l.id}.json</button>)}
        <button onClick={() => setArquivo({ titulo: 'estilos/elementos.json', conteudo: bib?.elementos })} className="truncate rounded-lg px-2 py-1 text-left hover:bg-white/5">📄 estilos/elementos.json</button>
      </div>
    </details>

    {arquivo && <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4" onClick={() => setArquivo(null)}>
      <div className="cartao max-h-[85vh] w-full max-w-2xl overflow-auto p-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center"><code className="text-sm">{arquivo.titulo}</code><button onClick={() => setArquivo(null)} className="ml-auto text-nevoa hover:text-white">✕</button></div>
        <pre className="mt-3 whitespace-pre-wrap text-xs text-nevoa">{JSON.stringify(arquivo.conteudo, (k, v) => (k === 'previa' ? undefined : v), 1)}</pre>
      </div>
    </div>}

    {montando && bib && <div className="fixed inset-y-0 right-0 z-30 w-full max-w-md overflow-y-auto border-l border-white/10 bg-card p-5 text-sm shadow-2xl">
      <div className="flex items-center"><h3 className="text-xl">Montar meu estilo</h3><button onClick={() => setMontando(false)} className="ml-auto text-nevoa hover:text-white" title="Fechar (o que você escolheu fica guardado)">✕</button></div>
      <p className="mt-1 text-xs text-nevoa">Junte uma legenda com os elementos que quiser. Com este painel aberto, os botões dos cartões da página também entram aqui.</p>
      <div className="mt-4 grid gap-3">
        <input value={m.nome} onChange={e => setM({ ...m, nome: e.target.value })} placeholder="Nome (ex.: Tutorial com bolha)" className="rounded-xl bg-black/40 p-3 outline-none" />
        <input value={m.descricao} onChange={e => setM({ ...m, descricao: e.target.value })} placeholder="Para que serve (opcional)" className="rounded-xl bg-black/40 p-3 outline-none" />
        <div className="grid grid-cols-[110px_1fr] items-start gap-3">
          <div className="w-[110px]">{legSel && <PreviaVideo previa={legSel.previa} pedir={() => pedir(`legenda:${legSel.id}`)} />}</div>
          <div className="grid gap-2"><span className="text-nevoa">Legenda</span>
            <select value={m.legenda} onChange={e => setM({ ...m, legenda: e.target.value })} className="rounded-full border border-white/15 bg-marinho px-3 py-1.5">{bib.legendas.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}</select>
            <span className="text-nevoa">Cor de destaque</span>
            <div className="flex flex-wrap gap-1.5">{CORES.map(([c, n]) => <button key={c} title={n} onClick={() => setM({ ...m, cor_destaque: c })} className={`h-7 w-7 rounded-full border-2 ${m.cor_destaque === c ? 'border-white' : 'border-transparent'}`} style={{ background: c }} />)}</div>
            {!['#F79615', '#E9760D'].includes(m.cor_destaque) && <span className="text-[11px] text-amber-200">Fora da paleta da Grava Simples: bom para cliente ou teste.</span>}
          </div>
        </div>
        {(['animacao', 'elemento'] as const).map(c => <div key={c}><div className="mb-1 text-nevoa">{c === 'animacao' ? 'Animações' : 'Elementos na tela'}</div>
          <div className="flex flex-wrap gap-1.5">{bib.elementos.filter(e => e.categoria === c).map(e => <button key={e.id} onClick={() => alterna(e.id)} title={e.descricao} className={chip(m.elementos.includes(e.id))}>{m.elementos.includes(e.id) ? '✓ ' : ''}{e.nome}</button>)}
            {c === 'elemento' && <button onClick={() => setM({ ...m, trilha: !m.trilha })} title="Primeira música de trilhas/ por baixo da voz, abaixando quando há fala" className={chip(m.trilha)}>{m.trilha ? '✓ ' : ''}Trilha automática</button>}
          </div></div>)}
        <div className="grid grid-cols-2 gap-3">
          <label className="grid gap-1 text-nevoa">Transição (locução e slides)<select value={m.transicao} onChange={e => setM({ ...m, transicao: e.target.value })} className="rounded-full border border-white/15 bg-marinho px-3 py-1.5 text-white"><option value="">fade (padrão)</option>{bib.elementos.filter(e => e.categoria === 'transicao').map(e => <option key={e.id} value={e.id}>{e.nome}</option>)}</select></label>
          <label className="grid gap-1 text-nevoa">Formato preferido<select value={m.formato} onChange={e => setM({ ...m, formato: e.target.value })} className="rounded-full border border-white/15 bg-marinho px-3 py-1.5 text-white"><option value="">o do vídeo</option>{bib.elementos.filter(e => e.categoria === 'formato').map(e => <option key={e.id} value={e.id}>{e.nome}</option>)}</select></label>
        </div>
        <div><div className="mb-1 text-nevoa">Combina com</div><div className="flex flex-wrap gap-1.5">{bib.temas.map(t => <button key={t.id} onClick={() => setM({ ...m, temas: m.temas.includes(t.id) ? m.temas.filter(x => x !== t.id) : [...m.temas, t.id] })} className={chip(m.temas.includes(t.id))}>{t.rotulo}</button>)}</div></div>
        <div className="text-xs text-nevoa">Fica no nível <b className="text-white">{NIVEL[nivelPrev]}</b>. Depois de salvar, o estilo ganha a prévia completa e aparece no Novo pedido.</div>
        <div className="flex items-center gap-2"><button onClick={salvar} disabled={!m.nome.trim() || salvando} className="btn-laranja px-5 py-2">{salvando ? 'Salvando…' : 'Salvar estilo'}</button><button onClick={() => setM(VAZIO)} className={btn}>Limpar</button></div>
        {erro && <span className="text-red-300">{erro}</span>}
      </div>
    </div>}
  </div>
}
