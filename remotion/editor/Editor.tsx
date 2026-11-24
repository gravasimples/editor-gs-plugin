// Editor manual do Editor GS (12/11/2026). Prévia = a mesma composição Montagem que o motor renderiza, com as mesmas props; editar aqui é editar o
// projeto que o agente montou (projeto.json). "Renderizar" manda as props ao gateway, que refaz o vídeo com o motor e grava uma versão nova.
// Fase 1: transições por corte, textos e grafismos (texto, tempo, mover na linha do tempo), legenda (corrigir palavra), efeitos sonoros, trilha
// (volume/sem trilha), zoom/clarão/barra, gancho e tela final, desfazer. Fase 2 (12/11): aparar/mover/apagar trechos da EDL (tudo que tem tempo
// acompanha: edl.ts; a prévia toca os trechos direto do bruto; o render recorta o bruto de novo) e trocar o estilo inteiro da legenda.
// Depois: keyframes, filtros, máscara, batida.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Player, type PlayerRef } from '@remotion/player'
import { Montagem } from '../src/Montagem'
import type { Grafismo, LegendaCineticaCfg, MontagemProps } from '../src/tipos'
import { limites, mapaIntervalo, mesmaEdl, offsets, remapearProps, type Trecho } from './edl'

type Frase = { i: number; texto: string; inicio: number; fim: number }
type EstiloLeg = { id: string; nome: string; descricao: string; cinetica: boolean; fora_da_marca: boolean; legenda: Record<string, any> }
type EdlInfo = { disponivel: boolean; motivo?: string; manter?: Trecho[]; duracao_bruto_s?: number; arquivo_bruto?: string; recuperada?: string | null; tem_palavras?: boolean }
type LinhaPrev = { inicio: number; fim: number; palavras: { texto: string; inicio: number; fim: number }[] }
type LegPrev = { linhas: LinhaPrev[]; cinetica: LegendaCineticaCfg | null; estilo: Record<string, any>; aviso?: string | null }
type Projeto = { props: MontagemProps; frases: Frase[]; edl_info?: EdlInfo; legenda_estilos?: EstiloLeg[]; legenda_atual?: { id: string | null; modo: 'ass' | 'cinetica' | 'nenhuma'; legenda: Record<string, any> }
  midia_base: string; arquivos_base: string; conversa: string; video_final: string; sfx_catalogo: string[]
  capcut?: { estado: 'exportando' | 'pronto' | 'falhou'; nome?: string; erro?: string; avisos?: string[]; transicoes?: string[]; tempo_s?: number } | null
  acabamento: { trilha?: string | null; trilha_original?: string | null; trilha_volume_db?: number | null }; versoes?: { arquivo: string; quando: string }[]
  render?: { estado: string; arquivo?: string; erro?: string; tempo_s?: number; etapa?: string; avisos?: string[] } | null }
type Sel = { tipo: 'plano' | 'grafismo' | 'frase' | 'sfx' | 'trecho'; i: number } | null
type Estado = { props: MontagemProps; correcoes: Record<number, string>; acab: { trilha_volume_db: number; sem_trilha: boolean }
  edl: Trecho[] | null      // fase 2: trechos do bruto na ordem do vídeo (null = projeto sem EDL/bruto)
  leg_estilo: string | null // fase 2: estilo de legenda escolhido (null = o que o projeto já tem)
}

const TRANSICOES: [string, string][] = [['seco', 'Corte seco'], ['punch', 'Punch (zoom rápido)'], ['tremor', 'Tremor'], ['zoom_blur', 'Zoom com desfoque'], ['deslize', 'Deslize'], ['giro', 'Giro'], ['luz', 'Luz vazando'], ['flash', 'Flash branco']]
const ROT_TRANS = Object.fromEntries(TRANSICOES)
const TIPOS_GRAF: Record<string, string> = { kicker: 'Chamada', manchete: 'Manchete', pilula: 'Pílula', riscado: 'Riscado', checklist: 'Checklist', pilulas: 'Pílulas', fluxo: 'Fluxo', cartoes: 'Cartões', numero: 'Número', logos: 'Logos', ondas: 'Ondas', cta: 'CTA', serie: 'Abertura da série' }
const fmt = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, '0')}`
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x))

export function Editor({ conversa, projeto }: { conversa: string; projeto: string }) {
  const [proj, setProj] = useState<Projeto | null>(null); const [erro, setErro] = useState('')
  const [est, setEst] = useState<Estado | null>(null); const [hist, setHist] = useState<Estado[]>([])
  const [sel, setSel] = useState<Sel>(null); const [aba, setAba] = useState<'selecao' | 'legenda' | 'som' | 'geral'>('selecao')
  const [t, setT] = useState(0); const [legendaPrevia, setLegendaPrevia] = useState(true); const [enviando, setEnviando] = useState(false)
  const player = useRef<PlayerRef>(null)
  const url = `/api/gs/conversas/${conversa}/projetos/${encodeURIComponent(projeto)}`

  const carregar = useCallback(async (inicial = false) => {
    const r = await fetch(url); if (!r.ok) { setErro((await r.json().catch(() => ({}))).detail || `Erro ${r.status}`); return }
    const d: Projeto = await r.json(); (window as any).remotion_staticBase = d.midia_base; setProj(d)
    if (inicial) { setEst({ props: d.props, correcoes: {}, acab: { trilha_volume_db: d.acabamento?.trilha_volume_db ?? -20, sem_trilha: !d.acabamento?.trilha },
      edl: d.edl_info?.disponivel && d.edl_info.manter ? d.edl_info.manter : null, leg_estilo: null }); setHist([]) }
  }, [url])
  useEffect(() => { carregar(true) }, [carregar])
  useEffect(() => {  // acompanha o envio ao CapCut
    if (proj?.capcut?.estado !== 'exportando') return
    const id = setInterval(() => carregar(), 4000); return () => clearInterval(id)
  }, [proj?.capcut?.estado, carregar])
  const recarregar = useRef(false)  // depois do render: o projeto salvo (vídeo recortado, legenda refeita) vira o novo ponto de partida, se nada mudou no meio
  useEffect(() => {  // acompanha o render em andamento
    if (proj?.render?.estado !== 'renderizando') { if (recarregar.current && proj?.render) { recarregar.current = false; if (!histRef.current.length) carregar(true) } return }
    const id = setInterval(() => carregar(), 3000); return () => clearInterval(id)
  }, [proj?.render?.estado, carregar])
  useEffect(() => {
    const p = player.current; if (!p) return
    const f = () => setT(p.getCurrentFrame() / (est?.props.fps || 30)); p.addEventListener('frameupdate', f); return () => p.removeEventListener('frameupdate', f)
  }, [est?.props.fps, proj])

  const histRef = useRef<Estado[]>([]); histRef.current = hist
  const mudar = (fn: (e: Estado) => void) => setEst(e => { if (!e) return e; setHist(h => [...h.slice(-49), e]); const n = clone(e); fn(n); return n })
  const ajustar = (fn: (e: Estado) => void) => setEst(e => { if (!e) return e; const n = clone(e); fn(n); return n })  // arrastar: só o 1º movimento entra no desfazer
  const desfazer = () => setHist(h => { if (!h.length) return h; setEst(h[h.length - 1]); return h.slice(0, -1) })
  useEffect(() => { const k = (ev: KeyboardEvent) => { if ((ev.ctrlKey || ev.metaKey) && ev.key === 'z' && !(ev.target as HTMLElement).closest('input,textarea')) { ev.preventDefault(); desfazer() } }; addEventListener('keydown', k); return () => removeEventListener('keydown', k) }, [])

  const p = est?.props
  const vin = p?.vinheta?.ativo ? p.vinheta.duracao_s : 0
  const total = p ? p.duracao_s + vin + (p.tela_final?.ativo ? p.tela_final.duracao_s : 0) : 1
  const frames = p ? Math.ceil(total * p.fps) : 1
  const ir = (s: number) => player.current?.seekTo(Math.max(0, Math.round(s * (p?.fps || 30))))
  const edlSalva = proj?.edl_info?.disponivel ? proj.edl_info.manter || null : null
  const edlMudou = !!(est?.edl && edlSalva && !mesmaEdl(est.edl, edlSalva))
  const estiloMudou = !!(est?.leg_estilo && est.leg_estilo !== proj?.legenda_atual?.id)
  const frases = useMemo(() => (proj?.frases || []).flatMap(f => {  // frases da legenda salva, levadas para a EDL editada
    const texto = est?.correcoes[f.i] ?? f.texto
    if (!edlMudou || !edlSalva || !est?.edl) return [{ ...f, texto }]
    const n = mapaIntervalo(f.inicio, f.fim, edlSalva, est.edl); return n ? [{ ...f, ...n, texto }] : []
  }), [proj, est?.correcoes, est?.edl, edlMudou, edlSalva])
  const fraseAgora = frases.find(f => t >= f.inicio && t < f.fim)
  const mudou = hist.length > 0
  // prévia da legenda (fase 2): o servidor devolve as linhas no tempo da EDL editada e no estilo escolhido (ou a prop da cinética)
  const [legPrev, setLegPrev] = useState<LegPrev | null>(null)
  const estiloAlvo = proj?.legenda_estilos?.find(e => e.id === (est?.leg_estilo || proj?.legenda_atual?.id))
  const alvoCinetica = estiloAlvo ? estiloAlvo.cinetica : proj?.legenda_atual?.modo === 'cinetica'
  useEffect(() => {
    if (!proj || !est || !proj.edl_info?.tem_palavras || (proj.legenda_atual?.modo === 'nenhuma' && !est.leg_estilo)) { setLegPrev(null); return }
    const id = setTimeout(async () => {
      try {
        const r = await fetch(url + '/previa_legenda', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ edl: est.edl, estilo: est.leg_estilo, correcoes: est.correcoes }) })
        if (r.ok) setLegPrev(await r.json())
      } catch { /* a prévia da legenda é extra */ }
    }, 350)
    return () => clearTimeout(id)
  }, [url, proj, est?.edl, est?.leg_estilo, est?.correcoes])
  const pPlayer = useMemo(() => {
    if (!p) return p
    let q: MontagemProps = p
    if (edlMudou && est?.edl && proj?.edl_info?.arquivo_bruto) q = { ...q, previa_trechos: { src: `${proj.midia_base}/bruto/${encodeURIComponent(proj.edl_info.arquivo_bruto)}`, trechos: est.edl } }
    if (legPrev && (edlMudou || estiloMudou)) q = { ...q, legenda_cinetica: alvoCinetica ? legPrev.cinetica : null }
    return q
  }, [p, edlMudou, estiloMudou, est?.edl, proj, legPrev, alvoCinetica])
  const linhaAgora = !alvoCinetica && legPrev?.linhas.length ? legPrev.linhas.find(l => t >= l.inicio && t < l.fim) : null

  async function renderizar() {
    if (!est) return; setEnviando(true); setErro('')
    try {
      const corpo = { props: est.props, correcoes: est.correcoes, acabamento: est.acab, edl: edlMudou ? est.edl : null, legenda_estilo: estiloMudou ? est.leg_estilo : null }
      const r = await fetch(url + '/renderizar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) })
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Erro ${r.status}`)
      recarregar.current = true; setHist([]); await carregar()
    } catch (e: any) { setErro(e.message) } finally { setEnviando(false) }
  }

  const [legCapcut, setLegCapcut] = useState<'identica' | 'nativa'>('identica')
  async function mandarCapcut() {  // CapCut fiel (12/11/2026): usa o projeto salvo (a última versão renderizada)
    setErro('')
    try {
      const r = await fetch(url + '/capcut', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ legenda: legCapcut }) })
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Erro ${r.status}`)
      await carregar()
    } catch (e: any) { setErro(e.message) }
  }

  if (erro && !proj) return <div className="vazio">{erro}</div>
  if (!proj || !est || !p || !pPlayer) return <div className="vazio">Carregando o projeto…</div>
  const W = p.largura, H = p.altura, vertical = H > W
  const r = proj.render

  return <div className="editor">
    <header>
      <a href={`/c/${conversa}`} className="voltar">‹ Conversa</a>
      <div className="titulo">Editor manual <span>· {proj.video_final}</span></div>
      <div className="acoes">
        <button onClick={desfazer} disabled={!hist.length} title="Ctrl+Z">↶ Desfazer</button>
        <select value={legCapcut} onChange={e => setLegCapcut(e.target.value as any)} title="Legenda no CapCut" style={{ width: 'auto' }}>
          <option value="identica">Legenda igual à entrega</option><option value="nativa">Legenda em texto editável</option>
        </select>
        <button onClick={mandarCapcut} disabled={proj?.capcut?.estado === 'exportando'} title={mudou ? 'Vai a última versão renderizada: renderize antes para levar as mudanças' : 'Cria o projeto no CapCut desta máquina igual à entrega'}>
          {proj?.capcut?.estado === 'exportando' ? 'Mandando ao CapCut…' : 'Mandar ao CapCut'}</button>
        <button className="laranja" onClick={renderizar} disabled={enviando || r?.estado === 'renderizando'}>{r?.estado === 'renderizando' ? (r.etapa === 'renderizando' || !r.etapa ? 'Renderizando…' : 'Recortando…') : enviando ? 'Enviando…' : mudou ? '▶ Renderizar versão editada' : '▶ Renderizar'}</button>
      </div>
    </header>
    {erro && <div className="aviso erro">{erro}</div>}
    {r?.estado === 'pronto' && <div className="aviso ok">Versão pronta: <a href={`${proj.arquivos_base}/${r.arquivo}`} target="_blank" rel="noreferrer">{r.arquivo}</a>{r.tempo_s ? ` (${Math.round(r.tempo_s)} s)` : ''}. Ela também aparece na conversa.{(r.avisos || []).length ? ' Atenção: ' + r.avisos!.join(' · ') : ''}</div>}
    {r?.estado === 'falhou' && <div className="aviso erro">O render falhou: {r.erro}</div>}
    {proj.capcut?.estado === 'pronto' && <div className="aviso ok">No CapCut: "{proj.capcut.nome}" (feche e abra o CapCut para ver na lista).{(proj.capcut.avisos || []).length ? ' Atenção: ' + proj.capcut.avisos!.join(' · ') : ''}</div>}
    {proj.capcut?.estado === 'falhou' && <div className="aviso erro">O envio ao CapCut falhou: {proj.capcut.erro}</div>}

    <div className="corpo">
      <div className="palco">
        <div className={`moldura ${vertical ? 'vertical' : ''}`}>
          <Player ref={player} component={Montagem as any} inputProps={pPlayer} durationInFrames={frames} fps={p.fps} compositionWidth={W} compositionHeight={H}
            style={{ width: '100%', height: '100%' }} controls clickToPlay acknowledgeRemotionLicense />
          {legendaPrevia && !alvoCinetica && (linhaAgora ? <LegendaPrevia linha={linhaAgora} t={t} leg={legPrev!.estilo} W={W} H={H} />
            : fraseAgora && !legPrev?.linhas.length && <div className="legenda" style={{ fontSize: vertical ? '3.4cqw' : '2.2cqw' }}>{fraseAgora.texto}</div>)}
        </div>
        <label className="chk"><input type="checkbox" checked={legendaPrevia} onChange={e => setLegendaPrevia(e.target.checked)} /> mostrar legenda na prévia ({alvoCinetica ? 'a animada sai igual ao render' : 'fonte, cores, posição e destaque do estilo; a animação sai no render'})</label>
        {edlMudou && <div className="dica">Prévia dos cortes direto do bruto (pode engasgar na emenda; o render sai liso).</div>}
      </div>

      <aside>
        <nav>{(['selecao', 'legenda', 'som', 'geral'] as const).map(a => <button key={a} className={aba === a ? 'ativa' : ''} onClick={() => setAba(a)}>{{ selecao: 'Seleção', legenda: 'Legenda', som: 'Som', geral: 'Geral' }[a]}</button>)}</nav>
        <div className="painel">
          {aba === 'selecao' && <PainelSelecao sel={sel} est={est} mudar={mudar} setSel={setSel} ir={ir} vin={vin} t={t} durBruto={proj.edl_info?.duracao_bruto_s || 0} />}
          {aba === 'legenda' && <div>
            <h4>Estilo da legenda</h4>
            {(proj.legenda_estilos || []).length > 0 && proj.edl_info?.tem_palavras ? <>
              <select value={est.leg_estilo || proj.legenda_atual?.id || ''} onChange={e => { const v = e.target.value; mudar(n => { n.leg_estilo = v === proj.legenda_atual?.id ? null : v }) }}>
                {!proj.legenda_atual?.id && <option value="">{proj.legenda_atual?.modo === 'nenhuma' ? 'sem legenda' : 'estilo atual (fora da biblioteca)'}</option>}
                {proj.legenda_estilos!.map(e => <option key={e.id} value={e.id}>{e.nome}{e.cinetica ? ' (animada)' : ''}{e.fora_da_marca ? ' · fora da marca' : ''}{e.id === proj.legenda_atual?.id ? ' · atual' : ''}</option>)}
              </select>
              {estiloAlvo && <p className="dica">{estiloAlvo.descricao}</p>}
              {estiloMudou && <p className="dica">No render a legenda é refeita neste estilo a partir das palavras (as correções abaixo vão junto).</p>}
            </> : <p className="dica">Trocar o estilo precisa das palavras do bruto, que este projeto não guardou (entregas antigas sem EDL).</p>}
            {legPrev?.aviso && <p className="dica">Atenção: {legPrev.aviso}</p>}
            <h4>Texto</h4>
            <p className="dica">Corrija a palavra mantendo o mesmo número de palavras por frase (tempos e animação continuam). Para reescrever uma frase, peça ao Editor na conversa.</p>
            {frases.map(f => <div key={f.i} className={`frase ${fraseAgora?.i === f.i ? 'agora' : ''}`}>
              <button className="tempo" onClick={() => ir(f.inicio + 0.01)}>{fmt(f.inicio)}</button>
              <input value={f.texto} onChange={e => { const v = e.target.value; mudar(n => { n.correcoes[f.i] = v }) }}
                className={(proj.frases[f.i].texto.split(/\s+/).length !== f.texto.trim().split(/\s+/).length) ? 'invalido' : est.correcoes[f.i] !== undefined && est.correcoes[f.i] !== proj.frases[f.i].texto ? 'editado' : ''} />
            </div>)}
            {!frases.length && <p className="dica">Esta entrega não tem legenda separada (ou a legenda é a cinética, que vem nas props).</p>}
          </div>}
          {aba === 'som' && <PainelSom est={est} mudar={mudar} catalogo={proj.sfx_catalogo} t={t} vin={vin} ir={ir} temTrilha={!!(proj.acabamento?.trilha || proj.acabamento?.trilha_original)} />}
          {aba === 'geral' && <PainelGeral est={est} mudar={mudar} />}
        </div>
      </aside>
    </div>

    <LinhaDoTempo est={est} frases={frases} total={total} vin={vin} t={t} sel={sel} ir={ir} durBruto={proj.edl_info?.duracao_bruto_s || 0} semEdl={proj.edl_info?.disponivel ? '' : proj.edl_info?.motivo || 'sem EDL'}
      selecionar={s => { setSel(s); setAba(s.tipo === 'frase' ? 'legenda' : s.tipo === 'sfx' ? 'som' : 'selecao') }} mudar={mudar} ajustar={ajustar} />
    {proj.versoes && proj.versoes.length > 0 && <footer>Versões editadas: {proj.versoes.map(v => <a key={v.arquivo} href={`${proj.arquivos_base}/${v.arquivo}`} target="_blank" rel="noreferrer">{v.arquivo}</a>)}</footer>}
  </div>
}

function Num({ v, on, passo = 0.1, min, max }: { v: number; on: (n: number) => void; passo?: number; min?: number; max?: number }) {
  return <input type="number" value={Number.isFinite(v) ? Math.round(v * 100) / 100 : 0} step={passo} min={min} max={max} onChange={e => on(parseFloat(e.target.value) || 0)} />
}

// fase 2: operações na EDL (todas passam por remapearProps, então o desfazer volta tudo junto)
const novaEdl = (n: Estado, nova: Trecho[]) => { if (!n.edl) return; n.props = remapearProps(n.props, n.edl, nova); n.edl = nova }

function PainelTrecho({ k, est, mudar, setSel, ir, vin, durBruto }: { k: number; est: Estado; mudar: (fn: (e: Estado) => void) => void; setSel: (s: Sel) => void; ir: (s: number) => void; vin: number; durBruto: number }) {
  const ms = est.edl; if (!ms || !ms[k]) return null
  const m = ms[k]; const lim = limites(ms, k, durBruto); const off = offsets(ms)[k]
  const aparar = (lado: 'inicio' | 'fim', v: number) => mudar(n => {
    const nova = clone(n.edl!); const x = nova[k]; const l = limites(nova, k, durBruto)
    if (lado === 'inicio') x.inicio = Math.round(Math.min(Math.max(v, l.min), x.fim - 0.2) * 1000) / 1000
    else x.fim = Math.round(Math.max(Math.min(v, l.max), x.inicio + 0.2) * 1000) / 1000
    novaEdl(n, nova)
  })
  const mover = (d: number) => { const j = k + d; if (j < 0 || j >= ms.length) return; mudar(n => { const nova = clone(n.edl!); [nova[k], nova[j]] = [nova[j], nova[k]]; novaEdl(n, nova) }); setSel({ tipo: 'trecho', i: j }) }
  return <div>
    <h4>Trecho {k + 1} de {ms.length} · no vídeo em {fmt(off + vin)}</h4>
    <p className="dica">Tempo do bruto. A legenda, os textos, os efeitos sonoros e os planos da câmera acompanham: o que ficar fora do trecho some, o que vem depois anda junto.</p>
    <label>Entrada (s no bruto) · sobra até {fmt(lim.min)}</label>
    <div className="lado"><button onClick={() => aparar('inicio', m.inicio - 0.1)}>−0,1</button><Num v={m.inicio} passo={0.05} min={lim.min} max={m.fim - 0.2} on={v => aparar('inicio', v)} /><button onClick={() => aparar('inicio', m.inicio + 0.1)}>+0,1</button></div>
    <label>Saída (s no bruto) · sobra até {fmt(lim.max)}</label>
    <div className="lado"><button onClick={() => aparar('fim', m.fim - 0.1)}>−0,1</button><Num v={m.fim} passo={0.05} min={m.inicio + 0.2} max={lim.max} on={v => aparar('fim', v)} /><button onClick={() => aparar('fim', m.fim + 0.1)}>+0,1</button></div>
    <div className="lado" style={{ marginTop: 10 }}>
      <button onClick={() => aparar('inicio', lim.min)} disabled={m.inicio <= lim.min}>Puxar toda a sobra do início</button>
      <button onClick={() => aparar('fim', lim.max)} disabled={m.fim >= lim.max}>…do fim</button></div>
    <label>Duração: {(m.fim - m.inicio).toFixed(2)} s</label>
    <div className="lado"><button onClick={() => mover(-1)} disabled={k === 0}>◀ Mover para antes</button><button onClick={() => mover(1)} disabled={k === ms.length - 1}>Mover para depois ▶</button></div>
    <div className="lado" style={{ marginTop: 6 }}><button className="link" onClick={() => ir(off + vin + 0.01)}>Ir para o trecho</button>
      <button className="link perigo" disabled={ms.length < 2} onClick={() => { mudar(n => novaEdl(n, n.edl!.filter((_, j) => j !== k))); setSel(null) }}>Apagar o trecho</button></div>
  </div>
}

function PainelSelecao({ sel, est, mudar, setSel, ir, vin, t, durBruto }: { sel: Sel; est: Estado; mudar: (fn: (e: Estado) => void) => void; setSel: (s: Sel) => void; ir: (s: number) => void; vin: number; t: number; durBruto: number }) {
  const p = est.props
  if (sel?.tipo === 'trecho') return <PainelTrecho k={sel.i} est={est} mudar={mudar} setSel={setSel} ir={ir} vin={vin} durBruto={durBruto} />
  if (!sel) return <div className="dica">Clique num bloco da linha do tempo: trecho (aparar, mover, apagar; puxe as bordas), corte (transição), texto/grafismo, frase da legenda ou efeito sonoro. Arraste os blocos de texto para mudar o tempo; puxe a borda direita para mudar a duração.
    {(p.grafismos?.length || 0) > 0 && <><h4>Textos e grafismos</h4>{p.grafismos!.map((g, i) => <button key={i} className="item" onClick={() => { setSel({ tipo: 'grafismo', i }); ir(g.inicio + vin + 0.05) }}>{fmt(g.inicio + vin)} · {TIPOS_GRAF[g.tipo] || g.tipo}: {g.texto || g.rotulo || '—'}</button>)}</>}
  </div>
  if (sel.tipo === 'plano') {
    const pl = p.camera?.planos?.[sel.i]; if (!pl) return null
    return <div>
      <h4>Corte em {fmt(pl.inicio + vin)}</h4>
      <label>Transição de entrada</label>
      <div className="grade">{TRANSICOES.map(([k, r]) => <button key={k} className={pl.entrada === k ? 'ativa' : ''} onClick={() => mudar(n => { n.props.camera!.planos[sel.i].entrada = k })}>{r}</button>)}</div>
      <label>Intensidade</label><input type="range" min={0.3} max={1.6} step={0.1} value={pl.intensidade ?? 1} onChange={e => { const v = parseFloat(e.target.value); mudar(n => { n.props.camera!.planos[sel.i].intensidade = v }) }} />
      <label>Duração da transição (s)</label><Num v={pl.dur} passo={0.05} min={0.05} max={1.5} on={v => mudar(n => { n.props.camera!.planos[sel.i].dur = v })} />
      <label>Zoom do plano (início → fim)</label><div className="lado"><Num v={pl.z0} passo={0.01} on={v => mudar(n => { n.props.camera!.planos[sel.i].z0 = v })} /><Num v={pl.z1} passo={0.01} on={v => mudar(n => { n.props.camera!.planos[sel.i].z1 = v })} /></div>
      <button className="link" onClick={() => mudar(n => { n.props.camera!.planos.forEach(x => { if (x !== n.props.camera!.planos[0]) x.entrada = pl.entrada }) })}>Usar “{ROT_TRANS[pl.entrada] || pl.entrada}” em todos os cortes</button>
    </div>
  }
  if (sel.tipo === 'grafismo') {
    const g = p.grafismos?.[sel.i]; if (!g) return null
    const set = (fn: (x: Grafismo) => void) => mudar(n => fn(n.props.grafismos![sel.i]))
    return <div>
      <h4>{TIPOS_GRAF[g.tipo] || g.tipo} em {fmt(g.inicio + vin)}</h4>
      {g.texto !== undefined && <><label>Texto</label><textarea rows={2} value={g.texto} onChange={e => { const v = e.target.value; set(x => { x.texto = v }) }} /></>}
      {g.destaque !== undefined && <><label>Palavra em destaque (laranja)</label><input value={g.destaque} onChange={e => { const v = e.target.value; set(x => { x.destaque = v }) }} /></>}
      {g.rotulo !== undefined && <><label>Rótulo</label><input value={g.rotulo} onChange={e => { const v = e.target.value; set(x => { x.rotulo = v }) }} /></>}
      {g.itens && <><label>Itens</label>{g.itens.map((it, j) => <input key={j} value={it.texto || ''} onChange={e => { const v = e.target.value; set(x => { x.itens![j].texto = v }) }} />)}</>}
      <label>Início e fim (s, tempo do vídeo)</label><div className="lado"><Num v={g.inicio} on={v => set(x => { x.inicio = Math.max(0, v) })} /><Num v={g.fim} on={v => set(x => { x.fim = Math.max(x.inicio + 0.3, v) })} /></div>
      <label>Posição</label><div className="grade">{(['topo', 'centro', 'peito'] as const).map(k => <button key={k} className={g.posicao === k ? 'ativa' : ''} onClick={() => set(x => { x.posicao = k })}>{k}</button>)}</div>
      <label>Entrada</label><select value={g.entrada || ''} onChange={e => { const v = e.target.value as any; set(x => { x.entrada = v || undefined }) }}><option value="">padrão do tipo</option>{['mola', 'mascara', 'desfoque', 'deslize', 'elastico', 'cair', 'subir'].map(k => <option key={k}>{k}</option>)}</select>
      <label>Saída</label><select value={g.saida || ''} onChange={e => { const v = e.target.value as any; set(x => { x.saida = v || undefined }) }}><option value="">padrão do tipo</option>{['some', 'sobe', 'mascara', 'encolhe', 'desfoque', 'deslize'].map(k => <option key={k}>{k}</option>)}</select>
      <label className="chk"><input type="checkbox" checked={!!g.tela_cheia} onChange={e => { const v = e.target.checked; set(x => { x.tela_cheia = v }) }} /> tela cheia (esconde a legenda no trecho)</label>
      <div className="lado"><button className="link" onClick={() => mudar(n => { const c = clone(n.props.grafismos![sel.i]); const d = c.fim - c.inicio; c.inicio = Math.max(0, t - vin); c.fim = c.inicio + d; n.props.grafismos!.push(c) })}>Duplicar no ponto atual</button>
        <button className="link perigo" onClick={() => { mudar(n => { n.props.grafismos!.splice(sel.i, 1) }); setSel(null) }}>Apagar</button></div>
    </div>
  }
  return <div className="dica">Use a aba ao lado para editar.</div>
}

function PainelSom({ est, mudar, catalogo, t, vin, ir, temTrilha }: { est: Estado; mudar: (fn: (e: Estado) => void) => void; catalogo: string[]; t: number; vin: number; ir: (s: number) => void; temTrilha: boolean }) {
  const [novo, setNovo] = useState(catalogo.find(c => c.startsWith('whoosh')) || catalogo[0] || '')
  const sfx = est.props.sfx || []
  return <div>
    <h4>Trilha</h4>
    {temTrilha ? <>
      <label className="chk"><input type="checkbox" checked={!est.acab.sem_trilha} onChange={e => { const v = !e.target.checked; mudar(n => { n.acab.sem_trilha = v }) }} /> com trilha (abaixa sozinha quando ele fala)</label>
      <label>Volume da trilha: {est.acab.trilha_volume_db} dB</label><input type="range" min={-36} max={-8} step={1} value={est.acab.trilha_volume_db} onChange={e => { const v = parseFloat(e.target.value); mudar(n => { n.acab.trilha_volume_db = v }) }} />
      <p className="dica">A trilha entra no acabamento, depois do render: a prévia não toca a trilha.</p>
    </> : <p className="dica">Esta entrega saiu sem trilha. Para pôr trilha, peça ao Editor (pasta trilhas/).</p>}
    <h4>Efeitos sonoros ({sfx.length})</h4>
    <div className="lado"><select value={novo} onChange={e => setNovo(e.target.value)}>{catalogo.map(c => <option key={c}>{c}</option>)}</select>
      <button onClick={() => mudar(n => { (n.props.sfx ||= []).push({ arquivo: novo, inicio: Math.max(0, +(t - vin).toFixed(2)), volume: 0.5 }); n.props.sfx.sort((a, b) => a.inicio - b.inicio) })}>+ no ponto atual ({fmt(t)})</button></div>
    {sfx.map((s, i) => <div key={i} className="frase">
      <button className="tempo" onClick={() => ir(s.inicio + vin)}>{fmt(s.inicio + vin)}</button>
      <select value={s.arquivo} onChange={e => { const v = e.target.value; mudar(n => { n.props.sfx![i].arquivo = v }) }}>{catalogo.map(c => <option key={c}>{c}</option>)}</select>
      <input type="range" min={0} max={1} step={0.05} value={s.volume} title={`volume ${s.volume}`} onChange={e => { const v = parseFloat(e.target.value); mudar(n => { n.props.sfx![i].volume = v }) }} />
      <button className="link perigo" onClick={() => mudar(n => { n.props.sfx!.splice(i, 1) })}>✕</button>
    </div>)}
  </div>
}

function PainelGeral({ est, mudar }: { est: Estado; mudar: (fn: (e: Estado) => void) => void }) {
  const p = est.props
  return <div>
    {p.frase_impacto && <><h4>Gancho na tela</h4>
      <label>Frase</label><input value={p.frase_impacto.texto} onChange={e => { const v = e.target.value; mudar(n => { n.props.frase_impacto!.texto = v }) }} />
      <label>Destaque</label><input value={p.frase_impacto.destaque} onChange={e => { const v = e.target.value; mudar(n => { n.props.frase_impacto!.destaque = v }) }} />
      <button className="link perigo" onClick={() => mudar(n => { n.props.frase_impacto = null })}>Tirar o gancho</button></>}
    {p.tela_final && <><h4>Tela final</h4>
      <label className="chk"><input type="checkbox" checked={p.tela_final.ativo} onChange={e => { const v = e.target.checked; mudar(n => { n.props.tela_final!.ativo = v }) }} /> mostrar tela final</label>
      <label>Título</label><input value={p.tela_final.titulo} onChange={e => { const v = e.target.value; mudar(n => { n.props.tela_final!.titulo = v }) }} />
      <label>Destaque</label><input value={p.tela_final.destaque} onChange={e => { const v = e.target.value; mudar(n => { n.props.tela_final!.destaque = v }) }} />
      <label>Chamada (CTA)</label><input value={p.tela_final.cta} onChange={e => { const v = e.target.value; mudar(n => { n.props.tela_final!.cta = v }) }} /></>}
    <h4>Efeitos gerais</h4>
    {!p.camera && <><label className="chk"><input type="checkbox" checked={p.zoom.ativo} onChange={e => { const v = e.target.checked; mudar(n => { n.props.zoom.ativo = v }) }} /> zoom alternado por frase</label>
      <label>Força do zoom: {p.zoom.fator.toFixed(2)}</label><input type="range" min={1} max={1.3} step={0.01} value={p.zoom.fator} onChange={e => { const v = parseFloat(e.target.value); mudar(n => { n.props.zoom.fator = v }) }} />
      <label className="chk"><input type="checkbox" checked={p.clarao.ativo} onChange={e => { const v = e.target.checked; mudar(n => { n.props.clarao.ativo = v }) }} /> clarão nos cortes</label></>}
    <label className="chk"><input type="checkbox" checked={!!p.barra_progresso} onChange={e => { const v = e.target.checked; mudar(n => { n.props.barra_progresso = v }) }} /> barra de progresso</label>
    {(p.capitulos?.length || 0) > 0 && <><h4>Capítulos</h4>{p.capitulos!.map((c, i) => <input key={i} value={c.texto} onChange={e => { const v = e.target.value; mudar(n => { n.props.capitulos![i].texto = v }) }} />)}</>}
  </div>
}

function LegendaPrevia({ linha, t, leg, W, H }: { linha: LinhaPrev; t: number; leg: Record<string, any>; W: number; H: number }) {
  // prévia do estilo do motor ASS: fonte, tamanho, cores, contorno/caixa, posição e o destaque do karaokê (a palavra falada acende e fica)
  const vertical = H > W; const base = vertical ? 1080 : 1920
  const tam = Number(leg[vertical ? 'tamanho_9x16' : 'tamanho_16x9'] || 64); const cq = (px: number) => `${(px / base) * 100}cqw`
  const karaoke = (leg.modo || 'karaoke') === 'karaoke'; const contorno = leg.contorno || '#000921'
  const borda = leg.contorno_px != null ? Number(leg.contorno_px) : Math.max(2, Math.floor(tam / 14))
  const peso = /extra|black/i.test(leg.peso || 'ExtraBold') ? 800 : /bold/i.test(leg.peso || '') ? 700 : 400
  const fonte = leg.fonte && leg.fonte !== 'Inter' ? `'${leg.fonte}', InterGS, sans-serif` : 'InterGS, Inter, sans-serif'
  const pos: React.CSSProperties = leg.altura_pct != null ? { bottom: `${leg.altura_pct}%` } : leg.posicao === 'alta' ? { top: '22%' } : leg.posicao === 'centro' ? { top: '50%', transform: 'translateY(-50%)' } : { bottom: '12%' }
  const caixa: React.CSSProperties = leg.caixa ? { background: leg.cor_caixa || contorno, padding: `${cq(tam * 0.12)} ${cq(tam * 0.3)}`, borderRadius: cq(tam * 0.18), boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone' } : {}
  const digitar = leg.animacao === 'digitar'
  return <div style={{ position: 'absolute', left: '5.5%', right: '5.5%', textAlign: 'center', pointerEvents: 'none', ...pos }}>
    <span style={{ fontFamily: fonte, fontWeight: peso, fontSize: cq(tam), lineHeight: 1.15, letterSpacing: leg.espacamento ? cq(Number(leg.espacamento)) : undefined,
      WebkitTextStroke: leg.caixa ? undefined : `${cq(borda * 2)} ${contorno}`, paintOrder: 'stroke fill', textShadow: leg.caixa ? undefined : `0 ${cq(Math.max(1, tam / 30))} 0 ${contorno}80`, ...caixa }}>
      {linha.palavras.map((w, i) => <span key={i} style={{ color: karaoke && t >= w.inicio ? (leg.cor_destaque || '#F79615') : (leg.cor_texto || '#fff'), opacity: digitar && t < w.inicio ? 0 : 1 }}>{w.texto}{i < linha.palavras.length - 1 ? ' ' : ''}</span>)}
    </span>
  </div>
}

function LinhaDoTempo({ est, frases, total, vin, t, sel, ir, selecionar, mudar, ajustar, durBruto, semEdl }: { est: Estado; frases: Frase[]; total: number; vin: number; t: number; sel: Sel; ir: (s: number) => void
  selecionar: (s: NonNullable<Sel>) => void; mudar: (fn: (e: Estado) => void) => void; ajustar: (fn: (e: Estado) => void) => void; durBruto: number; semEdl: string }) {
  const caixa = useRef<HTMLDivElement>(null); const [zoom, setZoom] = useState(1)
  const p = est.props; const pct = (s: number) => `${(s / total) * 100}%`
  const arrastar = (ev: React.PointerEvent, i: number, modo: 'mover' | 'fim') => {
    ev.stopPropagation(); const el = caixa.current; if (!el) return
    const largura = el.scrollWidth; const x0 = ev.clientX; const g0 = clone(p.grafismos![i]); let primeiro = true
    const mover = (e: PointerEvent) => {
      const ds = ((e.clientX - x0) / largura) * total; if (Math.abs(ds) < 0.02) return
      const aplicar = (n: Estado) => { const g = n.props.grafismos![i]; if (modo === 'mover') { const d = g0.fim - g0.inicio; g.inicio = Math.max(0, +(g0.inicio + ds).toFixed(2)); g.fim = +(g.inicio + d).toFixed(2) } else g.fim = Math.max(g0.inicio + 0.3, +(g0.fim + ds).toFixed(2)) }
      if (primeiro) { mudar(aplicar); primeiro = false } else ajustar(aplicar)
    }
    const soltar = () => { removeEventListener('pointermove', mover); removeEventListener('pointerup', soltar) }
    addEventListener('pointermove', mover); addEventListener('pointerup', soltar)
  }
  const aparar = (ev: React.PointerEvent, k: number, lado: 'inicio' | 'fim') => {  // puxar a borda do trecho: tudo é recalculado a partir do estado do começo do gesto
    ev.stopPropagation(); ev.preventDefault(); const el = caixa.current; if (!el || !est.edl) return
    const largura = el.scrollWidth; const tot0 = total; const x0 = ev.clientX; const e0 = clone(est); let primeiro = true
    const mover = (e: PointerEvent) => {
      const ds = ((e.clientX - x0) / largura) * tot0; if (Math.abs(ds) < 0.02) return
      const nova = clone(e0.edl!); const m = nova[k]; const l = limites(nova, k, durBruto)
      if (lado === 'inicio') m.inicio = Math.round(Math.min(Math.max(e0.edl![k].inicio + ds, l.min), m.fim - 0.2) * 1000) / 1000
      else m.fim = Math.round(Math.max(Math.min(e0.edl![k].fim + ds, l.max), m.inicio + 0.2) * 1000) / 1000
      const aplicar = (n: Estado) => { n.props = remapearProps(e0.props, e0.edl!, nova); n.edl = nova }
      if (primeiro) { mudar(aplicar); primeiro = false } else ajustar(aplicar)
    }
    const soltar = () => { removeEventListener('pointermove', mover); removeEventListener('pointerup', soltar) }
    addEventListener('pointermove', mover); addEventListener('pointerup', soltar)
  }
  const offs = est.edl ? offsets(est.edl) : []
  const clicarFundo = (e: React.MouseEvent) => { const el = caixa.current; if (!el) return; const r = el.getBoundingClientRect(); ir(((e.clientX - r.left + el.scrollLeft) / el.scrollWidth) * total) }
  const ativo = (tipo: string, i: number) => sel?.tipo === tipo && sel.i === i ? 'sel' : ''
  return <div className="tempo-linha">
    <div className="tl-topo"><span>{fmt(t)} / {fmt(total)}</span><label>zoom <input type="range" min={1} max={8} step={0.5} value={zoom} onChange={e => setZoom(parseFloat(e.target.value))} /></label></div>
    <div className="tl-rotulos"><div>Trechos</div><div>Cortes</div><div>Textos</div><div>Legenda</div><div>Efeitos</div></div>
    <div className="tl-caixa" ref={caixa} onClick={clicarFundo}>
      <div className="tl-conteudo" style={{ width: `${zoom * 100}%` }}>
        <div className="faixa">{est.edl ? est.edl.map((m, k) => <div key={m.id} className={`bloco trecho ${ativo('trecho', k)}`} style={{ left: pct(offs[k] + vin), width: pct(m.fim - m.inicio) }}
          onClick={e => { e.stopPropagation(); selecionar({ tipo: 'trecho', i: k }); ir(offs[k] + vin + 0.01) }} title={`Trecho ${k + 1}: ${fmt(m.inicio)}–${fmt(m.fim)} do bruto (puxe as bordas para aparar)`}>
          <span className="alca esq" onPointerDown={e => { selecionar({ tipo: 'trecho', i: k }); aparar(e, k, 'inicio') }} onClick={e => e.stopPropagation()} />
          T{k + 1} · {fmt(m.inicio)}–{fmt(m.fim)}
          <span className="alca" onPointerDown={e => { selecionar({ tipo: 'trecho', i: k }); aparar(e, k, 'fim') }} onClick={e => e.stopPropagation()} /></div>)
          : <div className="tl-vazia" title={semEdl}>Aparar cortes indisponível: {semEdl}</div>}</div>
        <div className="faixa">{(p.camera?.planos || []).map((pl, i) => <div key={i} className={`bloco plano ${ativo('plano', i)}`} style={{ left: pct(pl.inicio + vin), width: pct(pl.fim - pl.inicio) }}
          onClick={e => { e.stopPropagation(); selecionar({ tipo: 'plano', i }); ir(pl.inicio + vin + 0.01) }} title={ROT_TRANS[pl.entrada] || pl.entrada}>{i > 0 ? (ROT_TRANS[pl.entrada] || pl.entrada) : 'início'}</div>)}
          {!p.camera && p.cortes_s.map((c, i) => <div key={i} className="marca" style={{ left: pct(c + vin) }} />)}</div>
        <div className="faixa">{(p.grafismos || []).map((g, i) => <div key={i} className={`bloco graf ${ativo('grafismo', i)}`} style={{ left: pct(g.inicio + vin), width: pct(Math.max(0.2, g.fim - g.inicio)) }}
          onPointerDown={e => { selecionar({ tipo: 'grafismo', i }); arrastar(e, i, 'mover') }} onClick={e => e.stopPropagation()} title={g.texto || g.tipo}>{g.texto || TIPOS_GRAF[g.tipo] || g.tipo}
          <span className="alca" onPointerDown={e => arrastar(e, i, 'fim')} /></div>)}</div>
        <div className="faixa">{frases.map(f => <div key={f.i} className={`bloco frase-b ${ativo('frase', f.i)}`} style={{ left: pct(f.inicio), width: pct(f.fim - f.inicio) }}
          onClick={e => { e.stopPropagation(); selecionar({ tipo: 'frase', i: f.i }); ir(f.inicio + 0.01) }} title={f.texto}>{f.texto}</div>)}</div>
        <div className="faixa">{(p.sfx || []).map((s, i) => <div key={i} className={`ponto ${ativo('sfx', i)}`} style={{ left: pct(s.inicio + vin) }} title={s.arquivo}
          onClick={e => { e.stopPropagation(); selecionar({ tipo: 'sfx', i }); ir(s.inicio + vin) }} />)}</div>
        <div className="cursor" style={{ left: pct(t) }} />
      </div>
    </div>
  </div>
}
