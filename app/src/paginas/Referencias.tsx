import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Concorrente, type Referencia } from '../api'

const PLAT: Record<string, string> = { instagram: 'Instagram', tiktok: 'TikTok', youtube: 'YouTube', facebook: 'Facebook', web: 'Link', arquivo: 'Arquivo' }
const STATUS: Record<string, string> = { baixando: 'baixando…', pronto: 'pronta', erro: 'erro no download' }

export default function Referencias() {
  const nav = useNavigate()
  const [aba, setAba] = useState<'refs' | 'conc' | 'perfil'>('refs')
  const [perfil, setPerfil] = useState<any>(null)
  useEffect(() => { if (aba === 'perfil' && !perfil) api.perfil(true).then(setPerfil).catch(e => setErro(e.message)) }, [aba])
  const [refs, setRefs] = useState<Referencia[]>([])
  const [conc, setConc] = useState<Concorrente[]>([])
  const [dest, setDest] = useState<Awaited<ReturnType<typeof api.destaques>> | null>(null)
  useEffect(() => { if (aba === 'conc' && !dest) api.destaques(120).then(setDest).catch(() => {}) }, [aba])
  async function produzirDestaque(url: string) { setOcupado('Preparando…'); try { const fd = new FormData(); fd.append('texto', url); const r = await api.novaReferencia(fd); setRefs([r, ...refs]); nav(`/novo?referencia=${encodeURIComponent(r.id)}`) } catch (e: any) { setErro(e.message) } finally { setOcupado('') } }
  async function guardarDestaque(url: string) { setOcupado('Guardando…'); try { const fd = new FormData(); fd.append('texto', url); const r = await api.novaReferencia(fd); setRefs([r, ...refs]); setAba('refs') } catch (e: any) { setErro(e.message) } finally { setOcupado('') } }
  const [texto, setTexto] = useState('')
  const [arquivos, setArquivos] = useState<File[]>([])
  const [erro, setErro] = useState('')
  const [ocupado, setOcupado] = useState('')
  const [aberta, setAberta] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const carregar = () => { api.referencias().then(setRefs).catch(e => setErro(e.message)); api.concorrentes().then(setConc).catch(() => {}) }
  useEffect(() => { carregar(); const t = setInterval(() => { if (refs.some(r => r.status === 'baixando')) carregar() }, 6000); return () => clearInterval(t) }, [refs.length])
  async function guardar() {
    setErro('')
    if (!texto.trim() && arquivos.length === 0) { setErro('Cole um link ou anexe um vídeo.'); return }
    setOcupado('Guardando…')
    try { const fd = new FormData(); fd.append('texto', texto); arquivos.forEach(a => fd.append('arquivos', a)); const r = await api.novaReferencia(fd); setTexto(''); setArquivos([]); setRefs([r, ...refs]) } catch (e: any) { setErro(e.message) } finally { setOcupado('') }
  }
  async function analisar(r: Referencia) {
    setOcupado('Criando pedido de análise…')
    try { const c = await api.referenciaAnalisar(r.id); nav(`/c/${c.id}`) } catch (e: any) { setErro(e.message) } finally { setOcupado('') }
  }
  function minhaVersao(r: Referencia) { nav(`/novo?referencia=${encodeURIComponent(r.id)}`) }
  async function apagar(r: Referencia) { if (!confirm(`Apagar a referência "${r.titulo}"?`)) return; try { await api.referenciaApagar(r.id); setRefs(refs.filter(x => x.id !== r.id)) } catch (e: any) { setErro(e.message) } }
  return <div className="max-w-4xl mx-auto px-4 py-8">
    <h2 className="text-2xl">Referências e concorrentes</h2>
    <p className="text-nevoa mt-2">Cole o link de um Reels, TikTok ou vídeo do YouTube que a gente gostou, ou anexe o vídeo. O Editor pode analisar por que funciona e escrever a nossa versão. Nada é copiado para as entregas.</p>
    <div className="flex gap-2 mt-5 flex-wrap">{(['refs', 'conc', 'perfil'] as const).map(a => <button key={a} onClick={() => setAba(a)} className={`rounded-full px-4 py-1.5 text-sm border ${aba === a ? 'border-laranja text-laranja' : 'border-white/15 text-nevoa hover:bg-white/5'}`}>{a === 'refs' ? `Referências (${refs.length})` : a === 'conc' ? `Concorrentes do GSI (${conc.length})` : 'Perfil do Thiago'}</button>)}</div>
    {aba === 'refs' && <>
      <div className="cartao p-4 mt-5">
        <textarea value={texto} onChange={e => setTexto(e.target.value)} rows={3} placeholder="Cole o link e, se quiser, escreva o que gostamos nele (o gancho, o corte, a tela dividida…)" className="w-full bg-transparent outline-none resize-none placeholder:text-nevoa" />
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <button onClick={() => inputRef.current?.click()} className="rounded-full border border-white/15 px-3 py-1.5 text-sm hover:bg-white/5">📎 Anexar vídeo</button>
          <input ref={inputRef} type="file" multiple accept="video/*,image/*" className="hidden" onChange={e => setArquivos([...arquivos, ...Array.from(e.target.files || [])])} />
          {arquivos.map((a, i) => <span key={i} className="selo">{a.name} <button onClick={() => setArquivos(arquivos.filter((_, j) => j !== i))} className="ml-1">✕</button></span>)}
          <button onClick={guardar} disabled={!!ocupado} className="btn-laranja ml-auto px-5 py-2">{ocupado || 'Guardar referência'}</button>
        </div>
        {erro && <div className="mt-3 text-sm text-red-300">{erro}</div>}
      </div>
      <div className="grid gap-3 mt-5">
        {refs.length === 0 && <div className="text-nevoa text-sm">Nenhuma referência ainda. Pelo celular: Compartilhar → Editor GS → "Guardar como referência".</div>}
        {refs.map(r => <div key={r.id} className="cartao p-4">
          <div className="flex gap-4">
            {r.capa ? <img src={`/referencias/${r.id}/${r.capa}`} alt="" className="w-24 h-32 object-cover rounded-lg bg-black/40" /> : <div className="w-24 h-32 rounded-lg bg-black/40 flex items-center justify-center text-2xl">🔗</div>}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap"><span className="selo">{PLAT[r.plataforma] || r.plataforma}</span><span className={`text-xs ${r.status === 'erro' ? 'text-red-300' : r.status === 'baixando' ? 'text-laranja animate-pulse' : 'text-nevoa'}`}>{STATUS[r.status] || r.status}</span>{r.duracao_s && <span className="text-xs text-nevoa">{Math.round(r.duracao_s)} s</span>}{r.analise && <span className="text-xs text-green-300">analisada</span>}</div>
              <div className="font-bold mt-1 truncate">{r.titulo}</div>
              {r.autor && <div className="text-xs text-nevoa">{r.autor}{r.visualizacoes ? ` · ${r.visualizacoes.toLocaleString('pt-BR')} views` : ''}</div>}
              {r.nota && <div className="text-sm mt-1">{r.nota}</div>}
              {r.url && <a href={r.url} target="_blank" rel="noreferrer" className="text-xs text-laranja break-all">{r.url}</a>}
              {r.erro && <div className="text-xs text-red-300 mt-1">{r.erro}</div>}
              <div className="flex flex-wrap gap-2 mt-3 text-sm">
                <button onClick={() => analisar(r)} disabled={!!ocupado} className="rounded-full border border-laranja/60 text-laranja px-3 py-1 hover:bg-laranja/10">{r.analise ? 'Analisar de novo' : 'Analisar com o Editor'}</button>
                <button onClick={() => minhaVersao(r)} className="btn-laranja px-3 py-1">Fazer a nossa versão</button>
                {r.video && <a href={`/referencias/${r.id}/${r.video}`} target="_blank" rel="noreferrer" className="rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">Ver vídeo</a>}
                {r.status === 'erro' && r.url && <button onClick={() => api.referenciaBaixar(r.id).then(carregar)} className="rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">Tentar baixar de novo</button>}
                {r.analise && <button onClick={() => setAberta(aberta === r.id ? null : r.id)} className="rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">{aberta === r.id ? 'Fechar análise' : 'Ler análise'}</button>}
                <button onClick={() => apagar(r)} className="ml-auto text-xs text-nevoa hover:text-red-300">Apagar</button>
              </div>
              {r.pedidos.length > 0 && <div className="text-xs text-nevoa mt-2">Pedidos: {r.pedidos.map(p => <a key={p.issue_id} href={`/c/${p.issue_id}`} className="text-laranja mr-2">{p.codigo} ({p.tipo})</a>)}</div>}
            </div>
          </div>
          {aberta === r.id && r.analise && <pre className="whitespace-pre-wrap text-sm text-nevoa mt-3 font-[Inter] border-t border-white/10 pt-3">{r.analise}</pre>}
        </div>)}
      </div>
    </>}
    {aba === 'perfil' && <div className="mt-5 text-sm">
      <p className="text-nevoa">Padrões do que já foi postado, lidos do banco do GSI (só leitura, números históricos). O Editor consulta este resumo antes de roteiro, legenda e carrossel.</p>
      {!perfil && <div className="text-nevoa mt-4">Calculando…</div>}
      {perfil?.erro && <div className="text-red-300 mt-4">{perfil.erro}</div>}
      {perfil && !perfil.erro && <div className="grid gap-3 mt-4">
        <div className="cartao p-4"><div className="font-bold">Formatos</div><div className="text-nevoa text-xs mt-1">{perfil.n_posts} posts de {perfil.periodo?.[0]} a {perfil.periodo?.[1]}{perfil.perfil ? ` · ${Number(perfil.perfil.followers).toLocaleString('pt-BR')} seguidores em ${perfil.perfil.captured_on}` : ''}</div>
          <table className="w-full mt-2 text-xs"><thead><tr className="text-nevoa"><th className="text-left">Tipo</th><th>Posts</th><th>Plays (mediana)</th><th>Likes</th><th>Coment.</th><th>Duração</th></tr></thead><tbody>{Object.entries(perfil.por_tipo).map(([t, r]: any) => <tr key={t}><td className="py-1">{t}</td><td className="text-center">{r.n}</td><td className="text-center">{r.mediana_plays ?? '-'}</td><td className="text-center">{r.mediana_likes ?? '-'}</td><td className="text-center">{r.mediana_comentarios ?? '-'}</td><td className="text-center">{r.mediana_duracao_s ? `${Math.round(r.mediana_duracao_s)} s` : '-'}</td></tr>)}</tbody></table>
          <div className="text-xs text-nevoa mt-2">Reels por duração: {Object.entries(perfil.faixas_duracao_reels || {}).map(([k, v]) => `${k}: ${v}`).join(' · ')} · likes por mil plays (mediana): {perfil.likes_por_mil_plays_mediana ?? '-'}</div></div>
        <div className="cartao p-4"><div className="font-bold">Reels com mais plays</div>{perfil.top_plays.map((p: any) => <div key={p.shortcode} className="flex gap-2 text-xs mt-2"><span className="text-nevoa w-20 shrink-0">{p.data}</span><span className="text-laranja w-16 shrink-0">{Number(p.plays).toLocaleString('pt-BR')}</span><span className="truncate">{p.gancho}</span><a href={p.url} target="_blank" rel="noreferrer" className="text-laranja ml-auto shrink-0">abrir</a><button onClick={() => { setTexto(p.url); setAba('refs') }} className="text-xs text-nevoa shrink-0">ref</button></div>)}</div>
        <div className="cartao p-4"><div className="font-bold">Posts com mais comentários</div>{perfil.top_comentarios.map((p: any) => <div key={p.shortcode} className="flex gap-2 text-xs mt-2"><span className="text-nevoa w-20 shrink-0">{p.data}</span><span className="w-16 shrink-0">{p.tipo}</span><span className="text-laranja w-12 shrink-0">{p.comentarios}</span><span className="truncate">{p.gancho}</span>{p.cta_comentario && <span className="selo shrink-0">CTA</span>}</div>)}</div>
        <div className="cartao p-4"><div className="font-bold">Carrosséis publicados</div>{perfil.carrosseis.map((p: any) => <div key={p.shortcode} className="flex gap-2 text-xs mt-2"><span className="text-nevoa w-20 shrink-0">{p.data}</span><span className="text-laranja w-20 shrink-0">{p.likes ?? '-'} likes</span><span className="truncate">{p.gancho}</span><a href={p.url} target="_blank" rel="noreferrer" className="text-laranja ml-auto shrink-0">abrir</a></div>)}</div>
        <div className="cartao p-4"><div className="font-bold">Hashtags mais usadas</div><div className="text-xs text-nevoa mt-2">{perfil.hashtags_top.map(([h, n]: any) => `#${h} (${n})`).join(' · ')}</div></div>
        <div className="cartao p-4"><div className="font-bold">YouTube: mais vistos</div>{perfil.youtube.top_views.map((v: any) => <div key={v.video_id} className="flex gap-2 text-xs mt-2"><span className="text-nevoa w-20 shrink-0">{v.data}</span><span className="text-laranja w-16 shrink-0">{Number(v.views).toLocaleString('pt-BR')}</span><span className="w-12 shrink-0">{v.retencao ? `${Math.round(v.retencao)}%` : ''}</span><span className="truncate">{v.titulo}</span></div>)}</div>
        {perfil.arquivo && <div className="text-xs text-nevoa">Resumo gravado para o Editor em {perfil.arquivo}</div>}
      </div>}
    </div>}
    {aba === 'conc' && <div className="mt-5">
      <div className="cartao p-4 mb-4">
        <div className="font-bold">Vídeos que deram certo nos canais acompanhados</div>
        <div className="text-xs text-nevoa mt-1">{dest?.nota || 'YouTube, últimos 120 dias: views do vídeo divididas pela mediana do próprio canal no período. Não é viralidade comprovada, é o que destoou dentro de cada canal.'}</div>
        {!dest && <div className="text-nevoa text-sm mt-3">Calculando…</div>}
        {dest?.erro && <div className="text-red-300 text-sm mt-3">{dest.erro}</div>}
        {dest && dest.itens.length === 0 && !dest.erro && <div className="text-nevoa text-sm mt-3">Nada acima de {dest.minimo}× a mediana nesse período.</div>}
        <div className="grid gap-2 mt-3">{dest?.itens.map(d => <div key={d.video_id} className="rounded-xl bg-black/30 p-3 text-sm flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1"><a href={d.url} target="_blank" rel="noreferrer" className="font-bold hover:text-laranja">{d.titulo}</a><div className="text-xs text-nevoa">{d.canal} · {d.publicado}{d.duracao_s ? ` · ${Math.round(d.duracao_s / 60)} min` : ''}{d.formato ? ` · ${d.formato}` : ''}</div></div>
          <div className="text-xs text-right"><div className="text-laranja font-bold">{d.razao}× a mediana</div><div className="text-nevoa">{d.views.toLocaleString('pt-BR')} views · canal {d.mediana_canal.toLocaleString('pt-BR')}</div></div>
          <button onClick={() => guardarDestaque(d.url)} disabled={!!ocupado} className="rounded-full border border-laranja/60 text-laranja px-3 py-1 text-xs hover:bg-laranja/10">Guardar como referência</button>
          <button onClick={() => produzirDestaque(d.url)} disabled={!!ocupado} title="Guarda como referência e abre o Novo pedido no fluxo Minha versão" className="btn-laranja px-3 py-1 text-xs">Produzir</button>
        </div>)}</div>
        {dest && dest.canais.length > 0 && <div className="text-xs text-nevoa mt-3">Canais lidos: {dest.canais.map(k => `${k.nome} (${k.videos} vídeos${k.mediana ? `, mediana ${Math.round(k.mediana).toLocaleString('pt-BR')}` : ', poucos vídeos'})`).join(' · ')}</div>}
      </div>
      <p className="text-nevoa text-sm">Fontes acompanhadas pelo sistema de inteligência (GSI): canais e perfis de concorrentes, parceiros e referências, com o que já foi coletado. Só leitura; o radar diário do GSI continua sendo quem lê e propõe. O radar do Instagram depende do app da Meta.</p>
      <div className="grid gap-2 mt-4">{conc.map(c => <div key={c.id} className="cartao p-3 flex flex-wrap items-center gap-3 text-sm">
        <span className="selo">{PLAT[c.plataforma] || c.plataforma}</span>
        <div className="min-w-0"><div className="font-bold">{c.nome || c.handle}</div><div className="text-xs text-nevoa">{[c.tipo, c.categoria].filter(Boolean).join(' · ')}{c.notas ? ` · ${c.notas}` : ''}</div></div>
        <div className="ml-auto text-xs text-nevoa">{c.itens} itens{c.ultimo ? ` · último ${c.ultimo.slice(0, 10)}` : ''}{!c.ativo ? ' · inativo' : ''}</div>
        {c.url && <a href={c.url} target="_blank" rel="noreferrer" className="text-laranja text-xs">abrir</a>}
        {c.url && <button onClick={() => setTexto(c.url || '')} className="text-xs rounded-full border border-white/15 px-2 py-0.5 hover:bg-white/5" title="Cole o link de um post desse perfil para guardar como referência">usar</button>}
      </div>)}{conc.length === 0 && <div className="text-nevoa text-sm">Nenhuma fonte encontrada no banco do GSI.</div>}</div>
    </div>}
  </div>
}
