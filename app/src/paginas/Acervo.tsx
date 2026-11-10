import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type AcervoBusca, type AcervoHit } from '../api'

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
const ORIGENS: [string, string][] = [['tudo', 'Tudo'], ['youtube', 'YouTube'], ['instagram', 'Instagram'], ['app', 'Entregas do app']]

export default function Acervo() {
  const nav = useNavigate()
  const [q, setQ] = useState(''); const [origem, setOrigem] = useState('tudo'); const [d, setD] = useState<AcervoBusca | null>(null)
  const [erro, setErro] = useState(''); const [ocupado, setOcupado] = useState(false); const [aberto, setAberto] = useState<string | null>(null); const [tocando, setTocando] = useState<string | null>(null)
  const [corte, setCorte] = useState({ inicio: '', fim: '', titulo: '', gancho: '' }); const [criando, setCriando] = useState(false)
  useEffect(() => { api.acervo('', origem).then(setD).catch(() => {}) }, [])
  async function buscar(e?: React.FormEvent) { e?.preventDefault(); if (!q.trim()) return; setOcupado(true); setErro(''); setAberto(null); try { setD(await api.acervo(q, origem)) } catch (e: any) { setErro(e.message) } finally { setOcupado(false) } }
  function abrir(h: AcervoHit, chave: string) { setAberto(chave); setCorte({ inicio: String(h.corte_sugerido.inicio), fim: String(h.corte_sugerido.fim), titulo: h.trecho.split(/[.!?]/)[0].slice(0, 70), gancho: '' }) }
  async function virarCorte(h: AcervoHit) {
    if (!confirm(h.fonte.origem === 'gsi' ? 'Baixar só este trecho do original (com 5 s de margem) e abrir um pedido no Clipador? Pode levar um minuto.' : 'Abrir um pedido no Clipador com este trecho da entrega?')) return
    setCriando(true); setErro('')
    try { const r = await api.acervoCorte({ fonte_id: h.fonte.id, inicio: corte.inicio, fim: corte.fim, titulo: corte.titulo, gancho: corte.gancho, q }); nav(`/c/${r.conversa.id}`) } catch (e: any) { setErro(e.message) } finally { setCriando(false) }
  }
  const f = d?.fontes
  return <div className="max-w-4xl mx-auto px-4 py-8">
    <h2 className="text-2xl">Busca por fala</h2>
    <p className="text-nevoa mt-2 text-sm">"Onde o Thiago fala de supressão de ruído?" Procura nas transcrições do GSI (vídeos e lives do YouTube, Reels do Instagram) e nas entregas transcritas aqui; devolve o trecho, o instante e um corte sugerido. "Virar corte" manda o trecho ao Clipador. Nada é publicado.</p>
    <form onSubmit={buscar} className="flex flex-wrap gap-2 mt-5">
      <input value={q} onChange={e => setQ(e.target.value)} placeholder="palavras ou frase, ex.: supressão de ruído" className="flex-1 min-w-[16rem] rounded-full border border-white/15 bg-card px-4 py-2" />
      <select value={origem} onChange={e => setOrigem(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-2 text-sm">{ORIGENS.map(([v, r]) => <option key={v} value={v}>{r}</option>)}</select>
      <button type="submit" disabled={ocupado || !q.trim()} className="btn-laranja px-5 py-2 disabled:opacity-40">{ocupado ? 'Buscando…' : 'Buscar'}</button>
    </form>
    {f && <div className="text-xs text-nevoa mt-2">{f.total} fontes transcritas: {f.youtube} do YouTube, {f.instagram} do Instagram, {f.app} entregas do app ({f.com_video_local} com vídeo local).</div>}
    {erro && <div className="text-red-300 text-sm mt-3">{erro}</div>}
    {d && d.q && <div className="mt-4 grid gap-2">
      {d.resultados.length === 0 && <div className="text-nevoa text-sm">Nenhum trecho com "{d.q}". Tente menos palavras ou um sinônimo.</div>}
      {d.resultados.map((h, i) => { const chave = `${h.fonte.id}-${h.inicio}`; return <div key={chave} className="cartao p-3 text-sm">
        <div className="flex flex-wrap items-center gap-2 text-xs"><span className="selo">{h.fonte.origem === 'app' ? 'entrega do app' : h.fonte.plataforma}{h.fonte.formato ? ` · ${h.fonte.formato}` : ''}</span><span className="text-nevoa">{h.fonte.data}</span>
          {h.fonte.url ? <a href={h.link || h.fonte.url} target="_blank" className="font-bold hover:underline truncate max-w-[28rem]">{h.fonte.titulo}</a> : h.fonte.conversa ? <Link to={`/c/${h.fonte.conversa}`} className="font-bold hover:underline truncate max-w-[28rem]">{h.fonte.codigo ? `${h.fonte.codigo} · ` : ''}{h.fonte.titulo}</Link> : <span className="font-bold">{h.fonte.titulo}</span>}
          <span className="ml-auto text-laranja font-mono" title={h.instante_tipo === 'exato' ? 'instante exato da palavra' : h.instante_tipo === 'aproximado' ? 'instante aproximado (a fonte só tem frases)' : 'início da frase'}>{h.instante_tipo === 'aproximado' ? '~' : ''}{mmss(h.instante ?? h.inicio)}</span><span className="text-nevoa">{'●'.repeat(h.pontos)}{'○'.repeat(3 - h.pontos)}</span></div>
        <div className="mt-1 text-white/85"><span className="text-nevoa">{h.antes} </span><span className="bg-laranja/20 rounded px-1">{h.trecho}</span><span className="text-nevoa"> {h.depois}</span></div>
        <div className="flex flex-wrap gap-2 mt-2 text-xs">
          {(h.embed || h.video_local) && <button onClick={() => setTocando(tocando === chave ? null : chave)} className="rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">{tocando === chave ? '■ fechar' : '▶ ver o trecho'}</button>}
          {h.link && <a href={h.link} target="_blank" className="rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">abrir no instante ↗</a>}
          {(h.fonte.origem === 'gsi' || h.video_local) && <button onClick={() => aberto === chave ? setAberto(null) : abrir(h, chave)} className="rounded-full border border-laranja/60 text-laranja px-3 py-1 hover:bg-laranja/10">✂ virar corte ({mmss(h.corte_sugerido.inicio)}–{mmss(h.corte_sugerido.fim)})</button>}
          {h.fonte.origem === 'app' && !h.video_local && <span className="text-nevoa">vídeo de origem não está mais em entrada/</span>}
        </div>
        {tocando === chave && <div className="mt-2 overflow-hidden rounded-2xl bg-black">
          {h.video_local
            ? <video src={`/api/gs/acervo/video?fonte_id=${encodeURIComponent(h.fonte.id)}#t=${Math.max(0, (h.instante ?? h.inicio) - 1)},${h.corte_sugerido.fim}`} controls autoPlay playsInline className="max-h-[60vh] w-full" />
            : <iframe src={h.embed || ''} title="trecho" allow="autoplay; encrypted-media" allowFullScreen className="aspect-video w-full" />}
        </div>}
        {aberto === chave && <div className="mt-2 grid gap-2 text-xs border-t border-white/10 pt-2">
          <div className="flex flex-wrap items-center gap-2"><span className="text-nevoa">Início (s)</span><input value={corte.inicio} onChange={e => setCorte({ ...corte, inicio: e.target.value })} className="w-24 rounded-full border border-white/15 bg-card px-3 py-1" /><span className="text-nevoa">Fim (s)</span><input value={corte.fim} onChange={e => setCorte({ ...corte, fim: e.target.value })} className="w-24 rounded-full border border-white/15 bg-card px-3 py-1" /><span className="text-nevoa">{(() => { const a = Number(corte.inicio), b = Number(corte.fim); return isFinite(a) && isFinite(b) && b > a ? `${Math.round(b - a)} s` : '' })()}</span></div>
          <input value={corte.titulo} onChange={e => setCorte({ ...corte, titulo: e.target.value })} placeholder="título do corte" className="rounded-full border border-white/15 bg-card px-3 py-1" />
          <input value={corte.gancho} onChange={e => setCorte({ ...corte, gancho: e.target.value })} placeholder="frase de impacto (opcional; o Editor propõe se vazio)" className="rounded-full border border-white/15 bg-card px-3 py-1" />
          <div className="flex gap-2"><button onClick={() => virarCorte(h)} disabled={criando} className="btn-laranja px-4 py-1.5 disabled:opacity-40">{criando ? (h.fonte.origem === 'gsi' ? 'Baixando o trecho e abrindo…' : 'Abrindo…') : 'Abrir pedido no Clipador'}</button><button onClick={() => setAberto(null)} className="rounded-full border border-white/15 px-3 py-1.5">cancelar</button></div>
        </div>}
      </div> })}
    </div>}
    {d && d.q && d.resultados.length > 0 && <p className="text-nevoa text-[11px] mt-3">{d.nota} ●●● frase inteira no segmento · ●●○ todas as palavras no segmento · ●○○ palavras no segmento e no seguinte. Até 3 trechos por fonte.</p>}
  </div>
}
