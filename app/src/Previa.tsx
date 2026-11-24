import { useEffect, useRef, useState, type Ref } from 'react'
import { Icone } from './Icones'
import type { Entrega } from './api'

// Prévia dos cartões (design fase 2, 17/11/2026): capa quando existe, senão o primeiro quadro do vídeo (carregado só quando o cartão aparece na tela),
// senão ícone e cor do tipo. Um elemento de mídia por cartão; no computador o vídeo toca mudo ao passar o mouse.

export const TIPOS: Record<string, { rotulo: string; icone: string; cor: string; fundo: string }> = {
  video: { rotulo: 'Vídeo', icone: 'video', cor: 'text-laranja', fundo: 'from-laranja/25 to-laranja/5' },
  carrossel: { rotulo: 'Carrossel', icone: 'carrossel', cor: 'text-[#8fa7ff]', fundo: 'from-azul/40 to-azul/5' },
  imagem: { rotulo: 'Imagem', icone: 'imagem', cor: 'text-[#8fa7ff]', fundo: 'from-azul/35 to-azul/5' },
  texto: { rotulo: 'Texto', icone: 'texto', cor: 'text-emerald-300', fundo: 'from-emerald-400/20 to-emerald-400/5' },
  editavel: { rotulo: 'Editável', icone: 'editavel', cor: 'text-violet-300', fundo: 'from-violet-400/20 to-violet-400/5' },
  audio: { rotulo: 'Áudio', icone: 'voz', cor: 'text-pink-300', fundo: 'from-pink-400/20 to-pink-400/5' },
  decisao: { rotulo: 'Decisão', icone: 'aprovacoes', cor: 'text-laranja', fundo: 'from-laranja/20 to-transparent' },
  arquivo: { rotulo: 'Arquivos', icone: 'arquivo', cor: 'text-nevoa', fundo: 'from-white/10 to-white/0' },
}

/** Tipo da entrega pelo que ela tem: vídeo > carrossel (2+ imagens) > imagem > texto > editável > arquivos. */
export function tipoDe(itens: Entrega[]): string {
  if (itens.some(i => i.tipo === 'video')) return 'video'
  const imgs = itens.filter(i => i.tipo === 'imagem' && i.nome !== 'capa.png').length
  if (imgs >= 2) return 'carrossel'
  if (imgs || itens.some(i => i.tipo === 'imagem')) return 'imagem'
  if (itens.some(i => i.tipo === 'texto')) return 'texto'
  if (itens.some(i => i.tipo === 'editavel')) return 'editavel'
  if (itens.some(i => i.tipo === 'audio')) return 'audio'
  return 'arquivo'
}

/** Escolhe capa e vídeo principais de uma lista de arquivos. */
export function midiaDe(itens: Entrega[]) {
  const videos = itens.filter(i => i.tipo === 'video')
  const video = videos.find(i => i.principal) || videos[0] || null
  const imgs = itens.filter(i => i.tipo === 'imagem')
  const capa = imgs.find(i => i.nome === 'capa.png') || imgs.find(i => /capa|slide-?0?1|thumb/i.test(i.nome)) || imgs[0] || null
  return { video, capa }
}

function useVisivel<T extends Element>() {
  const ref = useRef<T>(null); const [vis, setVis] = useState(false)
  useEffect(() => {
    const el = ref.current; if (!el || vis) return
    if (typeof IntersectionObserver === 'undefined') { setVis(true); return }
    const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { setVis(true); io.disconnect() } }, { rootMargin: '200px' })
    io.observe(el); return () => io.disconnect()
  }, [vis])
  return [ref, vis] as const
}

export function Previa({ capa, video, tipo = 'arquivo', className = 'aspect-[4/5]', tocavel = false, videoRef, onClick, rotulo }: {
  capa?: string | null; video?: string | null; tipo?: string; className?: string; tocavel?: boolean; videoRef?: Ref<HTMLVideoElement>; onClick?: () => void; rotulo?: string
}) {
  const [ref, vis] = useVisivel<HTMLDivElement>()
  const [tocando, setTocando] = useState(false); const [falhou, setFalhou] = useState(false); const [capaFalhou, setCapaFalhou] = useState(false)
  const hover = useRef<HTMLVideoElement>(null)
  const t = TIPOS[tipo] || TIPOS.arquivo
  const usarCapa = !!capa && !capaFalhou
  const semMidia = falhou || (!usarCapa && !video)
  const entrar = () => { if (!tocavel && hover.current && matchMedia('(hover: hover)').matches) hover.current.play().catch(() => {}) }
  const sair = () => { if (hover.current) { hover.current.pause() } }
  const clicar = () => { if (tocavel && video) setTocando(true); else onClick?.() }
  if (tocando && video) return <div className={`relative overflow-hidden bg-black ${className}`}><video ref={videoRef} src={video} controls autoPlay playsInline className="h-full w-full object-contain" /></div>
  return <div ref={ref} onMouseEnter={entrar} onMouseLeave={sair} onClick={clicar} role={onClick || tocavel ? 'button' : undefined}
    className={`group/previa relative overflow-hidden bg-gradient-to-br ${t.fundo} ${onClick || (tocavel && video) ? 'cursor-pointer' : ''} ${className}`}>
    {semMidia ? <div className={`absolute inset-0 flex flex-col items-center justify-center gap-2 ${t.cor}`}><Icone nome={t.icone} className="h-10 w-10 opacity-90" /><span className="text-[11px] uppercase tracking-wider opacity-80">{rotulo || t.rotulo}</span></div>
      : vis && (usarCapa ? <img src={capa!} alt="" loading="lazy" onError={() => { setCapaFalhou(true); if (!video) setFalhou(true) }} className="absolute inset-0 h-full w-full object-cover transition duration-300 group-hover/previa:scale-[1.03]" />
        : <video ref={hover} src={`${video}#t=0.8`} muted playsInline loop preload="metadata" onError={() => setFalhou(true)} className="absolute inset-0 h-full w-full object-cover" />)}
    {!semMidia && video && <span className="pointer-events-none absolute bottom-2 right-2 flex h-8 w-8 items-center justify-center rounded-full bg-black/55 text-white backdrop-blur transition group-hover/previa:bg-laranja group-hover/previa:text-marinho"><Icone nome="play" className="h-4 w-4" /></span>}
  </div>
}
