import { useEffect, useState } from 'react'
import { api, type ConversaDetalhe, type Publicacao, type PublicarEstado } from '../api'

const ROTULO: Record<string, string> = { instagram: 'Instagram', youtube: 'YouTube', tiktok: 'TikTok', facebook: 'Facebook', linkedin: 'LinkedIn', threads: 'Threads' }
const STATUS: Record<string, string> = { draft: 'rascunho na Publora', scheduled: 'agendado', pending: 'na fila', processing: 'publicando', published: 'publicado', failed: 'falhou', partially_published: 'parcialmente publicado' }

export default function Publicar({ c }: { c: ConversaDetalhe }) {
  const [est, setEst] = useState<PublicarEstado | null>(null)
  const [hist, setHist] = useState<Publicacao[]>([])
  const [contas, setContas] = useState<string[]>([])
  const [legenda, setLegenda] = useState('')
  const [titulo, setTitulo] = useState('')
  const [quando, setQuando] = useState('')
  const [arquivo, setArquivo] = useState('final_9x16.mp4')
  const [ocupado, setOcupado] = useState('')
  const [erro, setErro] = useState('')
  const [aberto, setAberto] = useState(false)
  const [ytAberto, setYtAberto] = useState(false)
  const [yt, setYt] = useState({ titulo: '', descricao: '', tags: '', privacidade: 'private', quando: '', capa: '' })
  const videos = c.entregas.filter(e => e.tipo === 'video' && e.principal).map(e => e.nome)
  const capas = c.entregas.filter(e => e.tipo === 'imagem' && e.nome.startsWith('capa')).map(e => e.nome)
  const [capa, setCapa] = useState('')
  useEffect(() => { if (capas.length && !capa) setCapa(capas[0]) }, [capas.length])
  useEffect(() => {
    api.publicarEstado().then(e => { setEst(e); if (contas.length === 0) setContas(e.publora.contas.filter(x => x.plataforma === 'instagram' && x.status === 'active').map(x => x.platformId)) }).catch(e => setErro(e.message))
    api.publicacoes(c.id).then(setHist).catch(() => {})
  }, [c.id])
  useEffect(() => {
    if (!legenda && c.post) setLegenda([c.post.descricao, c.post.hashtags].filter(Boolean).join('\n\n'))
    if (!titulo && c.post?.titulo) setTitulo(c.post.titulo)
    if (!yt.titulo && c.post) setYt(y => ({ ...y, titulo: c.post?.titulo || c.titulo, descricao: [c.post?.descricao, c.post?.hashtags].filter(Boolean).join('\n\n'), tags: (c.post?.hashtags || '').replace(/#/g, '').split(/\s+/).filter(Boolean).slice(0, 12).join(', ') }))
    if (videos.length && !videos.includes(arquivo)) setArquivo(videos[0])
  }, [c.post, c.entregas.length])
  async function mandar(agendar: boolean) {
    setErro('')
    if (contas.length === 0) { setErro('Escolha pelo menos uma conta.'); return }
    let iso = ''
    if (agendar) {
      if (!quando) { setErro('Escolha data e hora para agendar.'); return }
      iso = new Date(quando).toISOString()
      if (!confirm(`Agendar "${arquivo}" para ${new Date(quando).toLocaleString('pt-BR')} em ${contas.length} conta(s)? A Publora vai publicar sozinha nesse horário.`)) return
    }
    setOcupado(agendar ? 'Agendando…' : 'Enviando rascunho…')
    try { await api.publicar(c.id, { arquivo, legenda, plataformas: contas, quando: iso, titulo, capa: contas.some(p => p.startsWith('instagram')) ? capa : '' }); setHist(await api.publicacoes(c.id)) } catch (e: any) { setErro(e.message) } finally { setOcupado('') }
  }
  async function mandarYoutube() {
    setErro('')
    if (!yt.titulo.trim()) { setErro('Título obrigatório no YouTube.'); return }
    const iso = yt.quando ? new Date(yt.quando).toISOString() : ''
    const msg = iso ? `Subir "${arquivo}" no YouTube como privado e publicar sozinho em ${new Date(yt.quando).toLocaleString('pt-BR')}?` : `Subir "${arquivo}" no YouTube como ${yt.privacidade === 'public' ? 'PÚBLICO' : yt.privacidade === 'unlisted' ? 'não listado' : 'privado'}?`
    if (!confirm(msg + ' Cada upload gasta 1.600 da cota diária de 10.000.')) return
    setOcupado('Subindo para o YouTube… (pode levar alguns minutos)')
    try { await api.youtube(c.id, { arquivo, titulo: yt.titulo, descricao: yt.descricao, tags: yt.tags, privacidade: yt.privacidade, quando: iso, capa: yt.capa }); setHist(await api.publicacoes(c.id)); setYtAberto(false) } catch (e: any) { setErro(e.message) } finally { setOcupado('') }
  }
  async function drive() {
    setErro(''); setOcupado('Copiando para o Drive…')
    const lista = [...videos, ...c.entregas.filter(e => ['capa.png', 'post.md', 'relatorio.md', 'legenda.srt'].includes(e.nome)).map(e => e.nome)]
    try { await api.drive(c.id, lista); setHist(await api.publicacoes(c.id)) } catch (e: any) { setErro(e.message) } finally { setOcupado('') }
  }
  async function atualizar() { setOcupado('Consultando…'); try { setHist(await api.publicacoes(c.id, true)) } catch (e: any) { setErro(e.message) } finally { setOcupado('') } }
  if (videos.length === 0) return null
  return <div className="mt-4 rounded-xl bg-black/30 p-3 text-sm">
    <div className="flex items-center gap-2 flex-wrap">
      <div className="text-[11px] uppercase tracking-wide text-nevoa">Publicar e guardar</div>
      {est?.youtube?.conectado ? <button onClick={() => { setYtAberto(!ytAberto); setAberto(false) }} className="ml-auto rounded-full border border-laranja/60 text-laranja px-4 py-1.5 hover:bg-laranja/10">{ytAberto ? 'Fechar' : 'YouTube'}</button> : <a href="/estilos" title={est?.youtube?.pendencias?.join('; ') || 'Conecte o canal uma vez em Estilos'} className="ml-auto rounded-full border border-white/15 px-4 py-1.5 hover:bg-white/5 text-nevoa">Conectar YouTube</a>}
      <button onClick={() => { setAberto(!aberto); setYtAberto(false) }} className="rounded-full border border-laranja/60 text-laranja px-4 py-1.5 hover:bg-laranja/10">{aberto ? 'Fechar' : 'Agendar na Publora'}</button>
      <button onClick={drive} disabled={!!ocupado || !est?.drive.configurado} title={est?.drive.pendencias.join('; ')} className="rounded-full border border-white/15 px-4 py-1.5 hover:bg-white/5 disabled:opacity-40">Salvar no Drive</button>
    </div>
    {ytAberto && est?.youtube?.conectado && <div className="mt-3 grid gap-3">
      <div className="text-xs text-nevoa">Canal <span className="text-white">{est.youtube.canal?.titulo}</span> {est.youtube.canal?.handle} · direto pela API do Google, sem Publora. 9:16 vira Short; 16:9 vira vídeo normal.</div>
      {videos.length > 1 && <select value={arquivo} onChange={e => setArquivo(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1.5 w-fit">{videos.map(v => <option key={v} value={v}>{v}</option>)}</select>}
      <input value={yt.titulo} onChange={e => setYt({ ...yt, titulo: e.target.value })} maxLength={100} className="rounded-xl bg-black/40 p-3 outline-none" placeholder="Título (até 100 caracteres)" />
      <textarea value={yt.descricao} onChange={e => setYt({ ...yt, descricao: e.target.value })} rows={4} className="w-full rounded-xl bg-black/40 p-3 outline-none" placeholder="Descrição" />
      <input value={yt.tags} onChange={e => setYt({ ...yt, tags: e.target.value })} className="rounded-xl bg-black/40 p-3 outline-none" placeholder="Tags separadas por vírgula" />
      <div className="flex flex-wrap items-center gap-2">
        <select value={yt.privacidade} onChange={e => setYt({ ...yt, privacidade: e.target.value })} className="rounded-full border border-white/15 bg-card px-3 py-1.5"><option value="private">Privado</option><option value="unlisted">Não listado</option><option value="public">Público</option></select>
        <input type="datetime-local" value={yt.quando} onChange={e => setYt({ ...yt, quando: e.target.value })} className="rounded-full border border-white/15 bg-card px-3 py-1.5" title="Agendar: sobe privado e o YouTube publica nessa hora" />
        {capas.length > 0 && <label className="flex items-center gap-2 text-nevoa"><input type="checkbox" checked={!!yt.capa} onChange={e => setYt({ ...yt, capa: e.target.checked ? capas[0] : '' })} />Capa {capas[0]}</label>}
        <button onClick={mandarYoutube} disabled={!!ocupado} className="btn-laranja px-4 py-1.5">{yt.quando ? 'Subir e agendar' : 'Subir no YouTube'}</button>
      </div>
      <div className="text-xs text-nevoa">Nada sobe sem este clique. Cota: uns 6 uploads por dia. Capa personalizada só em canal verificado.</div>
    </div>}
    {est && !est.publora.configurado && <div className="text-nevoa mt-2">Publora: {est.publora.pendencias.join('; ')}</div>}
    {est && !est.drive.configurado && <div className="text-nevoa mt-1">Drive: {est.drive.pendencias.join('; ')}</div>}
    {aberto && est?.publora.configurado && <div className="mt-3 grid gap-3">
      <div className="flex flex-wrap gap-2">{est.publora.contas.map(x => <label key={x.platformId} className={`selo cursor-pointer ${contas.includes(x.platformId) ? 'ring-2 ring-laranja' : ''} ${x.status !== 'active' ? 'opacity-50' : ''}`}>
        <input type="checkbox" className="hidden" checked={contas.includes(x.platformId)} onChange={e => setContas(e.target.checked ? [...contas, x.platformId] : contas.filter(p => p !== x.platformId))} />
        {ROTULO[x.plataforma] || x.plataforma} · {x.usuario || x.nome}{x.status !== 'active' ? ' (reconectar)' : ''}</label>)}</div>
      {videos.length > 1 && <select value={arquivo} onChange={e => setArquivo(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1.5 w-fit">{videos.map(v => <option key={v} value={v}>{v}</option>)}</select>}
      <textarea value={legenda} onChange={e => setLegenda(e.target.value)} rows={5} className="w-full rounded-xl bg-black/40 p-3 outline-none" placeholder="Legenda do post" />
      {contas.some(p => p.startsWith('youtube')) && <input value={titulo} onChange={e => setTitulo(e.target.value)} maxLength={100} className="rounded-xl bg-black/40 p-3 outline-none" placeholder="Título no YouTube (até 100 caracteres)" />}
      {capas.length > 0 && contas.some(p => p.startsWith('instagram')) && <label className="flex items-center gap-2 text-nevoa"><input type="checkbox" checked={!!capa} onChange={e => setCapa(e.target.checked ? capas[0] : '')} />Usar <span className="text-white">{capas[0]}</span> como capa do Reels</label>}
      <div className="flex flex-wrap items-center gap-2">
        <input type="datetime-local" value={quando} onChange={e => setQuando(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1.5" />
        <button onClick={() => mandar(true)} disabled={!!ocupado} className="btn-laranja px-4 py-1.5">Agendar</button>
        <button onClick={() => mandar(false)} disabled={!!ocupado} className="rounded-full border border-white/15 px-4 py-1.5 hover:bg-white/5">Só salvar rascunho</button>
      </div>
      <div className="text-xs text-nevoa">Nada é publicado sem este clique. O rascunho fica na Publora para você revisar e agendar lá, se preferir.</div>
    </div>}
    {ocupado && <div className="text-nevoa mt-2 animate-pulse">{ocupado}</div>}
    {erro && <div className="text-red-300 mt-2">{erro}</div>}
    {hist.length > 0 && <div className="mt-3 grid gap-1">
      <div className="flex items-center"><span className="text-[11px] uppercase tracking-wide text-nevoa">Histórico</span><button onClick={atualizar} className="ml-auto text-xs text-laranja">Atualizar status</button></div>
      {hist.slice().reverse().map((h, i) => <div key={i} className="text-nevoa">
        {new Date(h.quando).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })} · {h.tipo === 'youtube' ? <>YouTube: <a href={h.url} target="_blank" rel="noreferrer" className="text-laranja">{h.url}</a> · <span className="text-white">{h.status === 'agendado' ? `agendado para ${h.publishAt ? new Date(h.publishAt).toLocaleString('pt-BR') : ''}` : h.status || h.privacidade}</span>{h.views != null && <> · {h.views} views</>}{h.capa_erro && <span className="text-red-300"> · capa recusada (canal sem capa personalizada)</span>}{h.erro_status && <span className="text-red-300"> · {h.erro_status}</span>}</> : h.tipo === 'drive'
          ? <>Drive: {h.arquivos?.length} arquivo(s) em {h.destino}{h.link && <> · <a href={h.link} target="_blank" rel="noreferrer" className="text-laranja">abrir pasta</a></>}</>
          : <>Publora: {h.arquivo} → {(h.plataformas || []).map(p => ROTULO[p.split('-')[0]] || p).join(', ')} · <span className="text-white">{STATUS[h.status || ''] || h.status}</span>{h.scheduledTime && <> para {new Date(h.scheduledTime).toLocaleString('pt-BR')}</>}{h.capa && <> · capa enviada</>}{h.posts?.filter(p => p.erro).map(p => <span key={p.plataforma} className="text-red-300"> · {p.plataforma}: {p.erro}</span>)}</>}
      </div>)}
    </div>}
  </div>
}
