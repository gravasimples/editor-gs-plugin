import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, PASTA_TESTES, type AprovacaoDecisao, type AprovacaoEntrega } from '../api'
import { ChipsEtiquetas } from '../Etiquetas'
import { AvisosMarca } from '../Revisao'
import { Icone } from '../Icones'
import { Carga, Esqueleto, ha, useCarga } from '../Estados'
import { Previa, TIPOS } from '../Previa'

// Aprovações em cartões (design fase 2, 17/11/2026): prévia que toca no próprio cartão, Aprovar e Pedir ajuste visíveis, detalhes recolhidos.
// Entregas: Aprovar / Pedir ajuste (não há "recusar entrega" na API; o ajuste reabre a conversa). Decisões: Aprovar / Recusar com motivo.
const tipoEntrega = (e: AprovacaoEntrega) => e.video ? 'video' : e.imagens.length >= 2 ? 'carrossel' : e.imagens.length || e.capa ? 'imagem' : e.textos.descricao || e.textos.titulo ? 'texto' : 'arquivo'
const ehTeste = (pasta?: string | null) => !!pasta && (pasta === PASTA_TESTES || /^testes?\b/i.test(pasta))

function CartaoEntrega({ e, sel, onSel, onFeito }: { e: AprovacaoEntrega; sel: boolean; onSel: (v: boolean) => void; onFeito: () => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [ajuste, setAjuste] = useState(''); const [seg, setSeg] = useState<number | null>(null); const [busy, setBusy] = useState(''); const [msg, setMsg] = useState('')
  const [modo, setModo] = useState<'' | 'ajuste' | 'detalhes'>(''); const [feito, setFeito] = useState('')
  const sair = (rotulo: string) => { setFeito(rotulo); setTimeout(onFeito, 650) }
  async function aprovar() { setBusy('ok'); setMsg(''); try { await api.aprovar(e.id); sair('Aprovada') } catch (x: any) { setMsg(x.message) } finally { setBusy('') } }
  async function pedir() { if (!ajuste.trim()) return; setBusy('aj'); setMsg(''); try { await api.pedirAjuste(e.id, ajuste, seg, e.video?.nome || ''); setAjuste(''); setSeg(null); sair('Ajuste enviado') } catch (x: any) { setMsg(x.message) } finally { setBusy('') } }
  const marcar = () => { if (video.current) { video.current.pause(); setSeg(Math.floor(video.current.currentTime)) } else setMsg('Dê play na prévia e pause no ponto do ajuste.') }
  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  const tipo = tipoEntrega(e); const t = TIPOS[tipo]
  const alerta = !e.revisao.ok && e.revisao.resumo.alta > 0
  return <div className={`cartao relative flex flex-col overflow-hidden border transition duration-500 ${feito ? 'scale-95 opacity-0' : ''} ${sel ? 'border-laranja/60' : 'border-white/5 hover:border-white/15'}`}>
    <div className="relative">
      <Previa capa={e.capa?.url || e.imagens[0]?.url} video={e.video?.url} tipo={tipo} tocavel={!!e.video} videoRef={video} className="aspect-[4/5]" />
      <label className="absolute left-2 top-2 flex h-7 w-7 cursor-pointer items-center justify-center rounded-full bg-black/60 backdrop-blur" title="Selecionar para aprovar em lote"><input type="checkbox" checked={sel} onChange={x => onSel(x.target.checked)} className="accent-[#F79615]" /></label>
      <span className={`pointer-events-none absolute right-2 top-2 inline-flex items-center gap-1 rounded-full bg-black/60 px-2 py-0.5 text-[10px] backdrop-blur ${t.cor}`}><Icone nome={t.icone} className="h-3 w-3" />{t.rotulo}</span>
      {alerta && <span className="pointer-events-none absolute bottom-2 left-2 rounded-full bg-red-500/80 px-2 py-0.5 text-[10px] font-bold text-white">revisor: {e.revisao.resumo.alta} alta</span>}
      {e.imagens.length > 1 && !e.video && <span className="pointer-events-none absolute bottom-2 right-2 rounded-full bg-black/60 px-2 py-0.5 text-[10px]">{e.imagens.length} imagens</span>}
      {feito && <div className="absolute inset-0 flex items-center justify-center bg-marinho/70 font-[Unbounded] text-laranja">{feito} ✓</div>}
    </div>
    <div className="flex flex-1 flex-col p-3">
      <Link to={`/c/${e.id}`} className="line-clamp-2 text-sm font-bold leading-snug hover:text-laranja">{e.titulo}</Link>
      <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px] text-nevoa">{e.codigo && <span>{e.codigo}</span>}<span>{e.status === 'in_review' ? 'em revisão' : 'entregue'} {ha(e.atualizado)}</span>{e.pasta && <span className="truncate">· {e.pasta}</span>}</div>
      {e.textos.gancho && <div className="mt-2 line-clamp-2 text-xs text-white/80">“{e.textos.gancho}”</div>}
      <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-3">
        <button onClick={aprovar} disabled={!!busy || !!feito} className="btn-laranja inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs"><Icone nome="aprovacoes" className="h-3.5 w-3.5" />{busy === 'ok' ? 'Aprovando…' : 'Aprovar'}</button>
        <button onClick={() => setModo(modo === 'ajuste' ? '' : 'ajuste')} className={`rounded-full border px-3 py-1.5 text-xs ${modo === 'ajuste' ? 'border-laranja text-laranja' : 'border-white/15 hover:bg-white/5'}`}>Pedir ajuste</button>
        <button onClick={() => setModo(modo === 'detalhes' ? '' : 'detalhes')} title="Textos, etiquetas e revisor de marca" className={`ml-auto rounded-full px-2 py-1.5 text-xs ${modo === 'detalhes' ? 'text-laranja' : 'text-nevoa hover:text-white'}`}>{modo === 'detalhes' ? 'fechar' : 'detalhes'}</button>
      </div>
      {modo === 'ajuste' && <div className="mt-2 grid gap-1.5">
        <textarea autoFocus value={ajuste} onChange={x => setAjuste(x.target.value)} onKeyDown={x => { if (x.key === 'Enter' && !x.shiftKey) { x.preventDefault(); pedir() } }} rows={2} placeholder="Ex.: tira o zoom, corta a pausa" className="w-full resize-none rounded-xl bg-black/40 px-3 py-2 text-xs outline-none" />
        <div className="flex flex-wrap items-center gap-1.5">
          {e.video && <button onClick={() => seg != null ? setSeg(null) : marcar()} title="Pause a prévia no ponto e marque o segundo" className={`rounded-full border px-2.5 py-1 text-[11px] ${seg != null ? 'border-laranja text-laranja' : 'border-white/15 text-nevoa'}`}>{seg != null ? `aos ${mmss(seg)} ×` : 'marcar o segundo'}</button>}
          <button onClick={pedir} disabled={!!busy || !ajuste.trim()} className="ml-auto rounded-full border border-white/15 px-3 py-1 text-xs hover:bg-white/5 disabled:opacity-40">{busy === 'aj' ? '…' : 'Enviar ajuste'}</button>
        </div>
      </div>}
      {modo === 'detalhes' && <div className="mt-2 grid gap-2 border-t border-white/5 pt-2 text-xs">
        <AvisosMarca r={e.revisao} compacto />
        {e.etiquetas && <ChipsEtiquetas e={e.etiquetas} />}
        {e.textos.titulo && <div><span className="text-nevoa">Título:</span> {e.textos.titulo}</div>}
        {e.textos.descricao && <details><summary className="cursor-pointer text-nevoa">Legenda</summary><pre className="mt-1 whitespace-pre-wrap font-sans">{e.textos.descricao}</pre></details>}
        {e.textos.pendencias && <details open><summary className="cursor-pointer text-laranja">Pendências do Editor</summary><pre className="mt-1 whitespace-pre-wrap font-sans">{e.textos.pendencias}</pre></details>}
        {!e.revisao.ok && <details open={e.revisao.resumo.alta > 0}><summary className="cursor-pointer text-nevoa">Revisor de marca ({e.revisao.avisos.length})</summary><div className="mt-1"><AvisosMarca r={e.revisao} /></div></details>}
      </div>}
      {msg && <div className="mt-2 text-xs text-laranja">{msg}</div>}
    </div>
  </div>
}

function CartaoDecisao({ d, onFeito }: { d: AprovacaoDecisao; onFeito: () => void }) {
  const [coment, setComent] = useState(''); const [busy, setBusy] = useState(''); const [msg, setMsg] = useState(''); const [feito, setFeito] = useState('')
  const motivo = useRef<HTMLInputElement>(null)
  async function decidir(acao: 'aceitar' | 'recusar') {
    if (acao === 'recusar' && !coment.trim()) { setMsg('Escreva o motivo para recusar.'); motivo.current?.focus(); return }
    setBusy(acao); setMsg('')
    try { await api.decidir(d.id, d.interacao.id, acao, coment); setFeito(acao === 'aceitar' ? 'Aprovado' : 'Recusado'); setTimeout(onFeito, 650) } catch (x: any) { setMsg(x.message) } finally { setBusy('') }
  }
  return <div className={`relative overflow-hidden rounded-[20px] border border-dashed border-laranja/50 bg-laranja/5 p-4 transition duration-500 ${feito ? 'scale-[.98] opacity-0' : ''}`}>
    <div className="flex flex-wrap items-center gap-2 text-[11px]"><span className="inline-flex items-center gap-1 rounded-full bg-laranja px-2 py-0.5 font-bold text-marinho"><Icone nome="aprovacoes" className="h-3 w-3" />espera sua decisão</span>
      <Link to={`/c/${d.id}`} className="truncate text-nevoa hover:text-white">{d.codigo ? `${d.codigo} · ` : ''}{d.titulo}</Link><span className="text-nevoa">{ha(d.atualizado)}</span></div>
    <div className="mt-2 font-[Unbounded] text-[15px] leading-snug">{d.interacao.titulo}</div>
    {d.interacao.resumo && <div className="mt-1 line-clamp-4 whitespace-pre-wrap text-sm text-nevoa">{d.interacao.resumo}</div>}
    {d.interacao.pergunta && <div className="mt-2 text-sm">{d.interacao.pergunta}</div>}
    <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
      <button onClick={() => decidir('aceitar')} disabled={!!busy || !!feito} className="btn-laranja inline-flex items-center gap-1.5 px-4 py-1.5"><Icone nome="aprovacoes" className="h-4 w-4" />{busy === 'aceitar' ? 'Aprovando…' : 'Aprovar'}</button>
      <input ref={motivo} value={coment} onChange={x => setComent(x.target.value)} placeholder="motivo ou ajuste (obrigatório para recusar)" className="min-w-0 flex-1 basis-48 rounded-full bg-black/40 px-3 py-1.5 text-xs outline-none" />
      <button onClick={() => decidir('recusar')} disabled={!!busy || !!feito} className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5">{busy === 'recusar' ? '…' : 'Recusar'}</button>
      <Link to={`/c/${d.id}`} className="text-xs text-nevoa hover:text-white">abrir conversa</Link>
    </div>
    {msg && <div className="mt-2 text-xs text-laranja">{msg}</div>}
    {feito && <div className="absolute inset-0 flex items-center justify-center bg-marinho/70 font-[Unbounded] text-laranja">{feito} ✓</div>}
  </div>
}

type Dados = { entregas: AprovacaoEntrega[]; decisoes: AprovacaoDecisao[]; n: number; antigas_sem_aprovacao?: number; dias_done?: number }
const FILTROS = [['', 'Tudo'], ['decisoes', 'Decisões'], ['video', 'Vídeos'], ['imagem', 'Imagens e carrosséis'], ['aviso', 'Com aviso do revisor']] as const

export default function Aprovacoes() {
  const { dados: d, setDados, erro: erroCarga, carregando, recarregar } = useCarga<Dados>(() => api.aprovacoes())
  const [erro, setErro] = useState(''); const [sel, setSel] = useState<Set<string>>(new Set()); const [lote, setLote] = useState(false)
  const [filtro, setFiltro] = useState<typeof FILTROS[number][0]>(''); const [pasta, setPasta] = useState(''); const [mostrarTestes, setMostrarTestes] = useState(false)
  const carregar = () => recarregar()
  useEffect(() => { if (d) setSel(s => new Set([...s].filter(id => d.entregas.some(e => e.id === id)))) }, [d])
  useEffect(() => { const t = window.setInterval(() => { if (document.visibilityState !== 'hidden') api.aprovacoes().then(setDados).catch(() => {}) }, 30000); return () => window.clearInterval(t) }, [])
  async function vistas() { if (sel.size === 0) return; setLote(true); try { await api.marcarVistas([...sel]); await carregar() } catch (e: any) { setErro(e.message) } finally { setLote(false) } }
  async function aprovarLote() { if (sel.size === 0 || !confirm(`Aprovar ${sel.size} entrega(s)?`)) return; setLote(true); try { const r = await api.aprovarLote([...sel]); if (r.erros.length) setErro(`${r.erros.length} falhou(aram)`); await carregar() } catch (e: any) { setErro(e.message) } finally { setLote(false) } }
  const base = (d?.entregas || []).filter(e => mostrarTestes || !ehTeste(e.pasta))
  const nTestes = (d?.entregas.length || 0) - base.length
  const pastas = Array.from(new Set(base.map(e => e.pasta || '').filter(Boolean)))
  const passa = (e: AprovacaoEntrega, f: string) => f === '' || (f === 'video' && !!e.video) || (f === 'imagem' && !e.video && (e.imagens.length > 0 || !!e.capa)) || (f === 'aviso' && !e.revisao.ok)
  const entregas = filtro === 'decisoes' ? [] : base.filter(e => passa(e, filtro) && (!pasta || e.pasta === pasta))
  const decisoes = filtro === '' || filtro === 'decisoes' ? (d?.decisoes || []) : []
  const conta = (f: string) => f === 'decisoes' ? (d?.decisoes.length || 0) : f === '' ? base.length + (d?.decisoes.length || 0) : base.filter(e => passa(e, f)).length
  const chip = (ativo: boolean) => `shrink-0 whitespace-nowrap rounded-full border px-3 py-1 text-xs transition ${ativo ? 'border-laranja bg-laranja/10 text-laranja' : 'border-white/10 text-nevoa hover:bg-white/5 hover:text-white'}`
  const nada = !!d && d.entregas.length === 0 && d.decisoes.length === 0
  return <div className="max-w-6xl mx-auto px-4 py-8">
    <div className="flex items-center gap-3 flex-wrap"><h2 className="text-2xl">Aprovações</h2>{d && d.n > 0 && <span className="rounded-full bg-laranja px-2.5 py-0.5 text-xs font-bold text-marinho">{d.n} esperando você</span>}
      {entregas.length > 1 && <button onClick={() => setSel(sel.size === entregas.length ? new Set() : new Set(entregas.map(e => e.id)))} className="ml-auto text-xs text-nevoa hover:text-white">{sel.size === entregas.length ? 'desmarcar todas' : 'marcar todas'}</button>}</div>
    <p className="text-nevoa mt-1 text-sm">Toque na prévia para assistir. Aprovar e Pedir ajuste funcionam aqui mesmo; o ajuste com o segundo marcado reabre a conversa.</p>
    {erro && <div className="text-red-300 text-sm mt-3">{erro}</div>}
    {d && !nada && <div className="mt-4 -mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0 items-center">
      {FILTROS.map(([k, r]) => <button key={k} onClick={() => setFiltro(k)} className={chip(filtro === k)}>{r} <span className="opacity-60">{conta(k)}</span></button>)}
      {pastas.length > 1 && <select value={pasta} onChange={e => setPasta(e.target.value)} className="shrink-0 rounded-full border border-white/10 bg-card px-3 py-1 text-xs text-nevoa"><option value="">Todas as pastas</option>{pastas.map(p => <option key={p} value={p}>{p}</option>)}</select>}
      {nTestes > 0 && <button onClick={() => setMostrarTestes(!mostrarTestes)} className={`${chip(mostrarTestes)} ml-auto`}>{mostrarTestes ? 'esconder testes' : `mostrar testes · ${nTestes}`}</button>}
    </div>}
    <Carga carregando={carregando} erro={erroCarga} semDados={!d} onTentar={carregar} esqueleto={<Esqueleto className="mt-5" n={6} />}
      vazio={nada ? { icone: 'aprovacoes', titulo: 'Tudo em dia', texto: 'Nenhuma entrega nem decisão esperando você. Quando o Editor terminar um pedido, ele aparece aqui para aprovar.', acao: { rotulo: 'Ver a Biblioteca', to: '/biblioteca' } } : null}>
      {decisoes.length > 0 && <div className="mt-5 grid gap-3 lg:grid-cols-2">{decisoes.map(x => <CartaoDecisao key={x.interacao.id} d={x} onFeito={carregar} />)}</div>}
      {filtro !== 'decisoes' && <>
        {entregas.length > 0 ? <div className="mt-5 grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{entregas.map(e => <CartaoEntrega key={e.id} e={e} sel={sel.has(e.id)} onSel={v => setSel(s => { const n = new Set(s); v ? n.add(e.id) : n.delete(e.id); return n })} onFeito={carregar} />)}</div>
          : d && !nada && <div className="mt-5 rounded-[20px] border border-dashed border-white/10 p-6 text-center text-sm text-nevoa">Nenhuma entrega com esse filtro. <button onClick={() => { setFiltro(''); setPasta('') }} className="text-laranja hover:underline">Ver tudo</button></div>}
        {!!d?.antigas_sem_aprovacao && <div className="text-nevoa text-[11px] mt-3">{d.antigas_sem_aprovacao} entrega(s) com mais de {d.dias_done} dias sem aprovação registrada ficam fora desta fila; estão na página <Link to="/pecas" className="text-laranja hover:underline">Peças</Link>.</div>}
      </>}
    </Carga>
    {sel.size > 0 && <div className="fixed inset-x-0 bottom-16 z-30 flex justify-center px-4 md:bottom-6 md:pl-[280px]">
      <div className="flex flex-wrap items-center gap-2 rounded-full border border-white/10 bg-[#071030]/95 px-3 py-2 text-sm shadow-2xl backdrop-blur animate-[gs-entra_.18s_ease-out]">
        <span className="px-1 text-xs text-nevoa">{sel.size} selecionada{sel.size > 1 ? 's' : ''}</span>
        <button onClick={aprovarLote} disabled={lote} className="btn-laranja px-4 py-1.5 text-xs">{lote ? '…' : `Aprovar ${sel.size}`}</button>
        <button onClick={vistas} disabled={lote} title="Tira da fila sem aprovar nem reprovar (só registro no app)" className="rounded-full border border-white/15 px-3 py-1.5 text-xs hover:bg-white/5">marcar como vistas</button>
        <button onClick={() => setSel(new Set())} className="rounded-full p-1.5 text-nevoa hover:text-white" aria-label="Limpar seleção"><Icone nome="fechar" className="h-4 w-4" /></button>
      </div></div>}
  </div>
}
