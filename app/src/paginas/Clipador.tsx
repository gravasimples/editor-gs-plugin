import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, type Referencia } from '../api'

const TIPOS: [string, string, string][] = [['live', 'Live', 'Transmissão do YouTube ou Instagram'], ['aula', 'Aula ou vídeo longo', 'Aula gravada, tutorial longo'], ['youtube', 'Vídeo do YouTube (link)', 'Cole o link; o vídeo é baixado'], ['call', 'Call, mentoria ou consultoria', 'Reunião gravada; regras de privacidade e autorização']]

export default function Clipador() {
  const nav = useNavigate()
  const [qs] = useSearchParams()
  const [kit, setKit] = useState(qs.get('kit') === '1')
  const [nReels, setNReels] = useState(3)
  const [pecas, setPecas] = useState<string[]>(['carrossel', 'stories', 'youtube'])
  const [tipo, setTipo] = useState('live')
  const [nota, setNota] = useState('')
  const [n, setN] = useState(10)
  const [enq, setEnq] = useState('auto')
  const [arquivos, setArquivos] = useState<File[]>([])
  const [refs, setRefs] = useState<Referencia[]>([])
  const [referencia, setReferencia] = useState('')
  const [erro, setErro] = useState('')
  const [progresso, setProgresso] = useState<number | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => { api.referencias().then(r => setRefs(r.filter(x => x.video && (x.duracao_s || 0) > 180))).catch(() => {}) }, [])
  async function enviar() {
    setErro('')
    const fd = new FormData(); fd.append('nota', nota + (enq !== 'auto' ? ` Enquadramento na edição: ${enq}.` : '')); fd.append('tipo_origem', tipo); fd.append('n', String(n))
    if (kit) { fd.append('modo', 'kit'); fd.append('n_reels', String(nReels)); fd.append('pecas', ['reels', ...pecas].join(',')) }
    arquivos.forEach(a => fd.append('arquivos', a)); if (referencia) fd.append('referencia', referencia)
    if (arquivos.length === 0 && !referencia && !/https?:\/\//.test(nota)) { setErro('Anexe o vídeo longo, cole um link na nota ou escolha uma referência.'); return }
    setProgresso(0)
    try { const c = await api.novoClipe(fd, setProgresso); nav(`/c/${c.id}`) } catch (e: any) { setErro(e.message) } finally { setProgresso(null) }
  }
  return <div className="max-w-3xl mx-auto px-4 py-8">
    <h2 className="text-2xl">Clipador</h2>
    <p className="text-nevoa mt-2">Mande uma live, aula, vídeo do YouTube ou call. O Editor transcreve, propõe os melhores cortes (gancho, motivo, nota) e você escolhe quais viram Reels. Cada corte escolhido vira um pedido de edição com o fluxo padrão e o Revisor.</p>
    <div className="flex gap-2 mt-5 flex-wrap">
      <button onClick={() => setKit(false)} className={`rounded-full px-4 py-1.5 text-sm border ${!kit ? 'border-laranja text-laranja' : 'border-white/15 text-nevoa hover:bg-white/5'}`}>✂ Propor cortes (eu escolho)</button>
      <button onClick={() => setKit(true)} className={`rounded-full px-4 py-1.5 text-sm border ${kit ? 'border-laranja text-laranja' : 'border-white/15 text-nevoa hover:bg-white/5'}`}>📦 Kit de derivação (tudo pronto)</button>
    </div>
    {kit && <div className="cartao p-4 mt-3 text-sm">
      <div className="text-nevoa">Num pedido só, o Editor escolhe os melhores trechos e já entrega os Reels editados, mais as peças marcadas. Você aprova o pacote inteiro. Leva mais tempo que um Reel (um pedido longo, 30 a 60 min).</div>
      <div className="flex flex-wrap items-center gap-2 mt-3">
        <label className="text-nevoa"><input type="number" min={1} max={5} value={nReels} onChange={e => setNReels(Math.max(1, Math.min(5, Number(e.target.value))))} className="w-12 bg-card border border-white/15 rounded-full px-2 py-1 text-center" /> Reels prontos</label>
        {([['carrossel', 'Carrossel'], ['stories', 'Stories (3 telas)'], ['youtube', 'Descrição e capítulos do YouTube']] as const).map(([id, t]) => <button key={id} onClick={() => setPecas(pecas.includes(id) ? pecas.filter(x => x !== id) : [...pecas, id])} className={`rounded-full border px-3 py-1.5 ${pecas.includes(id) ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/15 text-nevoa'}`}>{pecas.includes(id) ? '✓ ' : ''}{t}</button>)}
      </div>
      <div className="text-xs text-nevoa mt-2">Os outros trechos bons ficam na conversa para virar corte depois, como no modo normal.</div>
    </div>}
    <div className="grid sm:grid-cols-2 gap-3 mt-6">{TIPOS.map(([id, t, d]) => <button key={id} onClick={() => setTipo(id)} className={`cartao text-left p-4 hover:bg-card2 ${tipo === id ? 'ring-2 ring-laranja' : ''}`}><div className="font-bold">{t}</div><div className="text-sm text-nevoa mt-1">{d}</div></button>)}</div>
    {tipo === 'call' && <div className="mt-3 text-sm text-laranja">Call e mentoria: trechos com aluno ou cliente só viram conteúdo público com autorização registrada; o Editor marca quem aparece e evita dados pessoais na tela.</div>}
    <div className="cartao p-4 mt-4">
      <textarea value={nota} onChange={e => setNota(e.target.value)} rows={3} placeholder="O que buscar nos cortes (temas, perguntas, momentos) e, se for link, cole aqui…" className="w-full bg-transparent outline-none resize-none placeholder:text-nevoa" />
      <div className="flex flex-wrap items-center gap-2 mt-3">
        <button onClick={() => inputRef.current?.click()} className="rounded-full border border-white/15 px-3 py-1.5 text-sm hover:bg-white/5">📎 Anexar vídeo longo</button>
        <input ref={inputRef} type="file" accept="video/*,audio/*" className="hidden" onChange={e => setArquivos(Array.from(e.target.files || []))} />
        {refs.length > 0 && <select value={referencia} onChange={e => setReferencia(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1.5 text-sm"><option value="">Ou uma referência já baixada…</option>{refs.map(r => <option key={r.id} value={r.id}>{r.titulo} ({Math.round((r.duracao_s || 0) / 60)} min)</option>)}</select>}
        <select value={enq} onChange={e => setEnq(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1.5 text-sm" title="Como enquadrar no 9:16 na edição"><option value="auto">Enquadramento: auto</option><option value="rosto">Seguir o rosto</option><option value="falante">Seguir quem fala (2+ pessoas)</option><option value="dividido">Tela dividida (2 pessoas)</option><option value="tela">Tela com fundo desfocado</option></select>
        {!kit && <label className="text-sm text-nevoa">Até <input type="number" min={4} max={20} value={n} onChange={e => setN(Number(e.target.value))} className="w-14 bg-card border border-white/15 rounded-full px-2 py-1 text-center" /> cortes</label>}
        <button onClick={enviar} disabled={progresso !== null} className="btn-laranja ml-auto px-5 py-2">{progresso !== null ? 'Enviando…' : kit ? 'Montar o kit ➤' : 'Propor cortes ➤'}</button>
      </div>
      {arquivos.map(a => <div key={a.name} className="mt-2 text-sm text-nevoa">{a.name} · {(a.size / 1e6).toFixed(0)} MB</div>)}
      {progresso !== null && <div className="mt-3"><div className="h-2 rounded-full bg-white/10 overflow-hidden"><div className="h-full bg-laranja transition-all" style={{ width: `${progresso}%` }} /></div><div className="text-xs text-nevoa mt-1">{progresso < 100 ? `Enviando… ${progresso}%` : 'Criando o pedido…'}</div></div>}
      {erro && <div className="mt-3 text-sm text-red-300">{erro}</div>}
    </div>
    <p className="text-xs text-nevoa mt-4">Uma live de 1 h leva alguns minutos para transcrever. Os cortes aparecem na conversa, com caixas para escolher.</p>
  </div>
}
