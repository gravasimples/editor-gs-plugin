import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'

/** Teleprompter do modo "Gravo eu mesmo": rola o texto para gravar com velocidade, tamanho, espelho e tela cheia; funciona no celular.
 *  Abre com ?c=<id da conversa>&secao=<chave> (lê a seção da entrega em texto) ou com o texto colado aqui. Não grava nada. */
const CHAVE_PADRAO = 'gravar'

function limpar(t: string) {
  // tira marcações [VISUAL]/[FALA]/(…) e cabeçalhos; mantém linhas em branco como respiro
  return t.replace(/\[[^\]]*\]/g, '').replace(/^#+\s.*$/gm, '').replace(/^\s*[-*]\s+/gm, '').replace(/\*\*/g, '').replace(/[ \t]+$/gm, '').replace(/\n{3,}/g, '\n\n').trim()
}

export default function Teleprompter() {
  const loc = useLocation(); const nav = useNavigate()
  const q = new URLSearchParams(loc.search)
  const cid = q.get('c') || ''; const secao = q.get('secao') || CHAVE_PADRAO
  const [texto, setTexto] = useState<string>((loc.state as any)?.texto || '')
  const [titulo, setTitulo] = useState('')
  const [erro, setErro] = useState('')
  const [rodando, setRodando] = useState(false)
  const [contagem, setContagem] = useState(0)
  const [velocidade, setVelocidade] = useState(Number(localStorage.getItem('tp_vel') || 60))  // px/s
  const [fonte, setFonte] = useState(Number(localStorage.getItem('tp_fonte') || 44))
  const [espelho, setEspelho] = useState(false)
  const [editando, setEditando] = useState(!cid)
  const caixa = useRef<HTMLDivElement>(null); const raf = useRef<number | null>(null); const ultimo = useRef<number>(0); const pos = useRef(0)

  useEffect(() => {
    if (!cid) return
    api.conversa(cid).then(c => {
      setTitulo(c.titulo)
      const s = (c.textos || []).find(x => x.chave === secao) || (c.textos || []).find(x => x.chave.startsWith('roteiro')) || (c.textos || []).find(x => x.chave === 'gravar')
      if (s) setTexto(limpar(s.conteudo)); else setErro('Esta conversa ainda não tem "Texto para você gravar" nem roteiro. Peça ao Editor ou cole o texto abaixo.')
    }).catch(e => setErro(e.message))
  }, [cid, secao])
  useEffect(() => { localStorage.setItem('tp_vel', String(velocidade)); localStorage.setItem('tp_fonte', String(fonte)) }, [velocidade, fonte])

  const palavras = texto.trim() ? texto.trim().split(/\s+/).length : 0
  const estimado = Math.round(palavras / 2.4)  // ~145 palavras por minuto, ritmo de fala do Thiago

  function passo(ts: number) {
    if (!caixa.current) return
    if (ultimo.current) {
      pos.current += (velocidade * (ts - ultimo.current)) / 1000
      caixa.current.scrollTop = pos.current
      if (caixa.current.scrollTop + caixa.current.clientHeight >= caixa.current.scrollHeight - 1) { parar(); return }
    }
    ultimo.current = ts; raf.current = requestAnimationFrame(passo)
  }
  function iniciar() {
    if (rodando || contagem) return
    setContagem(3)
    let n = 3
    const t = window.setInterval(() => { n -= 1; setContagem(n); if (n <= 0) { window.clearInterval(t); setRodando(true); ultimo.current = 0; pos.current = caixa.current?.scrollTop || 0; raf.current = requestAnimationFrame(passo) } }, 1000)
  }
  function parar() { setRodando(false); if (raf.current) cancelAnimationFrame(raf.current); raf.current = null; ultimo.current = 0 }
  function reiniciar() { parar(); pos.current = 0; if (caixa.current) caixa.current.scrollTop = 0 }
  function alternar() { rodando ? parar() : iniciar() }
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.code === 'Space') { e.preventDefault(); alternar() } if (e.key === 'ArrowUp') setVelocidade(v => Math.min(200, v + 5)); if (e.key === 'ArrowDown') setVelocidade(v => Math.max(10, v - 5)); if (e.key === 'r') reiniciar() }
    window.addEventListener('keydown', k); return () => { window.removeEventListener('keydown', k); if (raf.current) cancelAnimationFrame(raf.current) }
  })
  useEffect(() => { if (rodando) { if (raf.current) cancelAnimationFrame(raf.current); ultimo.current = 0; raf.current = requestAnimationFrame(passo) } }, [velocidade])
  async function telaCheia() { const el = document.getElementById('tp-raiz'); if (!document.fullscreenElement) await el?.requestFullscreen?.().catch(() => {}); else await document.exitFullscreen?.() }

  return <div id="tp-raiz" className="min-h-screen bg-black text-white flex flex-col">
    <div className="flex flex-wrap items-center gap-2 px-3 py-2 text-xs bg-black/80 border-b border-white/10">
      <button onClick={() => nav(-1)} className="rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">← Voltar</button>
      <span className="font-bold">Teleprompter</span>{titulo && <span className="text-nevoa truncate max-w-[40vw]">{titulo}</span>}
      <span className="text-nevoa">{palavras} palavras · ~{Math.floor(estimado / 60)}:{String(estimado % 60).padStart(2, '0')} de fala</span>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1">Velocidade <input type="range" min={10} max={200} step={5} value={velocidade} onChange={e => setVelocidade(Number(e.target.value))} className="w-24 accent-[#F79615]" /> {velocidade}</label>
        <label className="flex items-center gap-1">Letra <input type="range" min={24} max={96} step={2} value={fonte} onChange={e => setFonte(Number(e.target.value))} className="w-20 accent-[#F79615]" /></label>
        <button onClick={() => setEspelho(!espelho)} className={`rounded-full border px-3 py-1 ${espelho ? 'border-laranja text-laranja' : 'border-white/15'}`} title="Para teleprompter de vidro na frente da câmera">Espelho</button>
        <button onClick={() => setEditando(!editando)} className={`rounded-full border px-3 py-1 ${editando ? 'border-laranja text-laranja' : 'border-white/15'}`}>Editar texto</button>
        <button onClick={telaCheia} className="rounded-full border border-white/15 px-3 py-1">Tela cheia</button>
        <button onClick={reiniciar} className="rounded-full border border-white/15 px-3 py-1" title="tecla R">↺</button>
        <button onClick={alternar} className="btn-laranja px-4 py-1" title="barra de espaço">{rodando ? 'Pausar' : (contagem ? String(contagem) : 'Começar')}</button>
      </div>
    </div>
    {erro && <div className="px-4 py-2 text-sm text-red-300">{erro}</div>}
    {editando && <textarea value={texto} onChange={e => setTexto(e.target.value)} rows={8} className="m-3 rounded-xl bg-white/5 p-3 text-sm outline-none" placeholder="Cole aqui o texto para gravar (uma frase por linha; linha em branco = respiro). Marcações entre colchetes são escondidas na rolagem." />}
    <div className="relative flex-1 min-h-0">
      <div className="pointer-events-none absolute left-0 right-0 top-[38%] h-[2px] bg-laranja/70 z-10" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[30%] bg-gradient-to-b from-black to-transparent z-[5]" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[25%] bg-gradient-to-t from-black to-transparent z-[5]" />
      {contagem > 0 && <div className="absolute inset-0 z-20 flex items-center justify-center text-[20vh] font-bold text-laranja/90">{contagem}</div>}
      <div ref={caixa} onClick={alternar} className="h-[calc(100vh-56px)] overflow-y-auto px-[6vw] cursor-pointer" style={{ transform: espelho ? 'scaleX(-1)' : undefined }}>
        <div style={{ height: '38vh' }} />
        <div className="whitespace-pre-wrap font-semibold leading-[1.35] text-center" style={{ fontSize: fonte }}>{limpar(texto) || 'Sem texto ainda.'}</div>
        <div style={{ height: '70vh' }} />
      </div>
    </div>
  </div>
}
