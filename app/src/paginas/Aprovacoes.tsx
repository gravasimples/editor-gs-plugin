import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type AprovacaoDecisao, type AprovacaoEntrega } from '../api'
import { ChipsEtiquetas } from '../Etiquetas'
import { AvisosMarca } from '../Revisao'

function CartaoEntrega({ e, sel, onSel, onFeito }: { e: AprovacaoEntrega; sel: boolean; onSel: (v: boolean) => void; onFeito: () => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [ajuste, setAjuste] = useState(''); const [seg, setSeg] = useState<number | null>(null); const [busy, setBusy] = useState(''); const [msg, setMsg] = useState('')
  async function aprovar() { setBusy('ok'); try { await api.aprovar(e.id); onFeito() } catch (x: any) { setMsg(x.message) } finally { setBusy('') } }
  async function pedir() { if (!ajuste.trim()) return; setBusy('aj'); try { await api.pedirAjuste(e.id, ajuste, seg, e.video?.nome || ''); setMsg('Pedido de ajuste enviado; o Editor reabre a conversa.'); setAjuste(''); setSeg(null); onFeito() } catch (x: any) { setMsg(x.message) } finally { setBusy('') } }
  const marcar = () => { if (video.current) setSeg(Math.floor(video.current.currentTime)) }
  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  return <div className={`cartao p-4 ${sel ? 'ring-1 ring-laranja/60' : ''}`}>
    <div className="flex flex-wrap items-center gap-2"><input type="checkbox" checked={sel} onChange={x => onSel(x.target.checked)} className="accent-[#F79615]" title="selecionar para aprovar em lote" /><Link to={`/c/${e.id}`} className="font-bold hover:underline truncate max-w-[28rem]">{e.titulo}</Link>{e.codigo && <span className="selo">{e.codigo}</span>}<span className="text-nevoa text-xs">{e.status === 'in_review' ? 'em revisão' : 'entregue'} · {e.atualizado?.slice(0, 16).replace('T', ' ')}</span><span className="ml-auto"><AvisosMarca r={e.revisao} compacto /></span></div>
    <div className="grid md:grid-cols-2 gap-3 mt-3">
      <div>{e.video ? <video ref={video} src={e.video.url} controls preload="metadata" className="w-full rounded-lg bg-black max-h-80" /> : e.imagens.length ? <div className="grid grid-cols-2 gap-1">{e.imagens.slice(0, 4).map(i => <img key={i.caminho} src={i.url} className="w-full rounded" />)}</div> : e.capa ? <img src={e.capa.url} className="w-full rounded" /> : <div className="text-nevoa text-xs">sem prévia</div>}
        {e.video && <div className="text-[11px] text-nevoa mt-1">Pause no ponto e toque em "marcar o segundo" para o ajuste levar o instante.</div>}</div>
      <div className="text-xs grid gap-2">
        {e.etiquetas && <ChipsEtiquetas e={e.etiquetas} />}
        {e.textos.gancho && <div><span className="text-nevoa">Gancho:</span> {e.textos.gancho}</div>}
        {e.textos.titulo && <div><span className="text-nevoa">Título:</span> {e.textos.titulo}</div>}
        {e.textos.descricao && <details><summary className="cursor-pointer text-nevoa">Legenda</summary><pre className="whitespace-pre-wrap font-sans mt-1">{e.textos.descricao}</pre></details>}
        {e.textos.pendencias && <details><summary className="cursor-pointer text-laranja">Pendências do Editor</summary><pre className="whitespace-pre-wrap font-sans mt-1">{e.textos.pendencias}</pre></details>}
        {!e.revisao.ok && <details open={e.revisao.resumo.alta > 0}><summary className="cursor-pointer text-nevoa">Revisor de marca ({e.revisao.avisos.length})</summary><div className="mt-1"><AvisosMarca r={e.revisao} /></div></details>}
      </div>
    </div>
    <div className="flex flex-wrap items-center gap-2 mt-3 text-sm">
      <button onClick={aprovar} disabled={!!busy} className="rounded-full border border-green-400/60 text-green-300 px-3 py-1.5 hover:bg-green-400/10">{busy === 'ok' ? '…' : '✓ Aprovar'}</button>
      <input value={ajuste} onChange={x => setAjuste(x.target.value)} onKeyDown={x => { if (x.key === 'Enter') pedir() }} placeholder="Pedir ajuste (ex.: tira o zoom, corta a pausa)…" className="flex-1 min-w-[14rem] rounded-full bg-black/40 px-3 py-1.5 text-xs outline-none" />
      {e.video && <button onClick={marcar} className={`rounded-full border px-3 py-1 text-xs ${seg != null ? 'border-laranja text-laranja' : 'border-white/15 text-nevoa'}`}>{seg != null ? `aos ${mmss(seg)} ×` : 'marcar o segundo'}</button>}
      {seg != null && <button onClick={() => setSeg(null)} className="text-xs text-nevoa">sem instante</button>}
      <button onClick={pedir} disabled={!!busy || !ajuste.trim()} className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5 disabled:opacity-40">{busy === 'aj' ? '…' : 'Enviar ajuste'}</button>
    </div>
    {msg && <div className="text-xs text-laranja mt-2">{msg}</div>}
  </div>
}

function CartaoDecisao({ d, onFeito }: { d: AprovacaoDecisao; onFeito: () => void }) {
  const [coment, setComent] = useState(''); const [busy, setBusy] = useState(false); const [msg, setMsg] = useState('')
  async function decidir(acao: 'aceitar' | 'recusar') { if (acao === 'recusar' && !coment.trim()) { setMsg('Escreva o motivo para recusar.'); return } setBusy(true); try { await api.decidir(d.id, d.interacao.id, acao, coment); onFeito() } catch (x: any) { setMsg(x.message) } finally { setBusy(false) } }
  return <div className="cartao p-4 border border-laranja/40">
    <div className="flex flex-wrap items-center gap-2"><span className="text-[11px] uppercase tracking-wide text-laranja">decisão</span><Link to={`/c/${d.id}`} className="font-bold hover:underline">{d.titulo}</Link>{d.codigo && <span className="selo">{d.codigo}</span>}</div>
    <div className="font-bold mt-2 text-sm">{d.interacao.titulo}</div>
    {d.interacao.resumo && <div className="text-sm text-nevoa mt-1 whitespace-pre-wrap">{d.interacao.resumo}</div>}
    {d.interacao.pergunta && <div className="text-sm mt-2">{d.interacao.pergunta}</div>}
    <div className="flex flex-wrap items-center gap-2 mt-3 text-sm"><button onClick={() => decidir('aceitar')} disabled={busy} className="btn-laranja px-4 py-1.5">Aprovar</button><input value={coment} onChange={x => setComent(x.target.value)} placeholder="motivo ou ajuste (obrigatório para recusar)" className="flex-1 min-w-[12rem] rounded-full bg-black/40 px-3 py-1.5 text-xs outline-none" /><button onClick={() => decidir('recusar')} disabled={busy} className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5">Recusar</button></div>
    {msg && <div className="text-xs text-laranja mt-2">{msg}</div>}
  </div>
}

export default function Aprovacoes() {
  const [d, setD] = useState<{ entregas: AprovacaoEntrega[]; decisoes: AprovacaoDecisao[]; n: number; antigas_sem_aprovacao?: number; dias_done?: number } | null>(null); const [erro, setErro] = useState(''); const [sel, setSel] = useState<Set<string>>(new Set()); const [lote, setLote] = useState(false)
  const carregar = () => api.aprovacoes().then(x => { setD(x); setSel(s => new Set([...s].filter(id => x.entregas.some(e => e.id === id)))) }).catch(e => setErro(e.message))
  useEffect(() => { carregar(); const t = window.setInterval(carregar, 30000); return () => window.clearInterval(t) }, [])
  async function vistas() { if (sel.size === 0) return; setLote(true); try { await api.marcarVistas([...sel]); await carregar() } catch (e: any) { setErro(e.message) } finally { setLote(false) } }
  async function aprovarLote() { if (sel.size === 0 || !confirm(`Aprovar ${sel.size} entrega(s)?`)) return; setLote(true); try { const r = await api.aprovarLote([...sel]); if (r.erros.length) setErro(`${r.erros.length} falhou(aram)`); await carregar() } catch (e: any) { setErro(e.message) } finally { setLote(false) } }
  return <div className="max-w-5xl mx-auto px-4 py-8">
    <div className="flex items-center gap-3 flex-wrap"><h2 className="text-2xl">Aprovações</h2>{d && <span className="selo">{d.n} esperando você</span>}
      {d && d.entregas.length > 1 && <button onClick={() => setSel(sel.size === d.entregas.length ? new Set() : new Set(d.entregas.map(e => e.id)))} className="ml-auto text-xs text-nevoa hover:text-white">{sel.size === d.entregas.length ? 'desmarcar todas' : 'marcar todas'}</button>}
      {sel.size > 0 && <button onClick={aprovarLote} disabled={lote} className="rounded-full border border-green-400/60 text-green-300 px-3 py-1.5 text-sm hover:bg-green-400/10">{lote ? '…' : `✓ Aprovar ${sel.size} em lote`}</button>}
      {sel.size > 0 && <button onClick={vistas} disabled={lote} title="Tira da fila sem aprovar nem reprovar (só registro no app)" className="rounded-full border border-white/15 px-3 py-1.5 text-sm hover:bg-white/5">marcar {sel.size} como vistas</button>}</div>
    <p className="text-nevoa mt-2 text-sm">Tudo que espera você, num lugar só: entregas para aprovar (com prévia, textos, etiquetas e o revisor de marca) e decisões que o Editor pediu (plano de cenas, cortes). Pedir ajuste com o segundo marcado reabre a conversa. Nada sai do app: sem link externo, sem escrita no Notion.</p>
    {erro && <div className="text-red-300 text-sm mt-3">{erro}</div>}
    {!d && <div className="text-nevoa mt-4">…</div>}
    {d && d.decisoes.length > 0 && <div className="mt-5 grid gap-3"><div className="text-xs uppercase tracking-wide text-nevoa">Decisões pendentes ({d.decisoes.length})</div>{d.decisoes.map(x => <CartaoDecisao key={x.interacao.id} d={x} onFeito={carregar} />)}</div>}
    {d && <div className="mt-6 grid gap-3"><div className="text-xs uppercase tracking-wide text-nevoa">Entregas para aprovar ({d.entregas.length})</div>
      {d.entregas.map(e => <CartaoEntrega key={e.id} e={e} sel={sel.has(e.id)} onSel={v => setSel(s => { const n = new Set(s); v ? n.add(e.id) : n.delete(e.id); return n })} onFeito={carregar} />)}
      {d.entregas.length === 0 && <div className="text-nevoa text-sm">Nada esperando aprovação.</div>}
      {!!d.antigas_sem_aprovacao && <div className="text-nevoa text-[11px]">{d.antigas_sem_aprovacao} entrega(s) com mais de {d.dias_done} dias sem aprovação registrada ficam fora desta fila; estão na página <Link to="/pecas" className="text-laranja hover:underline">Peças</Link>.</div>}</div>}
  </div>
}
