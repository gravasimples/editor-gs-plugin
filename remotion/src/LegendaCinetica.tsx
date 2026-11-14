// Legenda cinética (10/11/2026): legenda palavra por palavra animada com GSAP dentro do Remotion.
// GSAP é gratuito desde 30/04/2025 (SplitText, CustomEase e CustomWiggle incluídos; docs/maquina/PESQUISA-GRAFISMOS-2026-11-10.md).
// Determinismo: o Remotion renderiza quadro a quadro, então nada aqui anda com o relógio. Cada linha monta uma timeline
// `paused: true` uma vez (SplitText divide a linha em palavras e letras) e, a cada quadro, `timeline.seek(t)` leva a animação
// ao instante exato do `useCurrentFrame`. O ticker do GSAP nunca avança a timeline (ela está pausada), e o DOM dividido
// pelo SplitText fica fora do React (texto estático por `dangerouslySetInnerHTML`, remontado por linha pela `key`).
import { useLayoutEffect, useMemo, useRef } from 'react'
import { AbsoluteFill } from 'remotion'
import gsap from 'gsap'
import { SplitText } from 'gsap/SplitText'
import { CustomEase } from 'gsap/CustomEase'
import { CustomWiggle } from 'gsap/CustomWiggle'
import type { LegendaCineticaCfg, LinhaLegenda } from './tipos'

gsap.registerPlugin(SplitText, CustomEase, CustomWiggle)
gsap.ticker.lagSmoothing(0)
// tremor: 7 oscilações que amortecem (CustomWiggle "easeOut"); registrado uma vez por bundle
if (!gsap.parseEase('gsTremor')) CustomWiggle.create('gsTremor', { wiggles: 7, type: 'easeOut' })

const escapar = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

/** Monta a timeline de uma linha. Tempos relativos ao início da linha. */
function montarTimeline(cfg: LegendaCineticaCfg, linha: LinhaLegenda, split: SplitText, cursor: HTMLElement | null, em: number): gsap.core.Timeline {
  const tl = gsap.timeline({ paused: true })
  const words = split.words as HTMLElement[]
  const n = Math.min(words.length, linha.palavras.length)
  const rel = (t: number) => Math.max(0, t - linha.inicio)
  const duracao = Math.max(0.1, linha.fim - linha.inicio)
  for (let i = 0; i < n; i++) {
    const w = words[i]; const p = linha.palavras[i]
    const ini = rel(p.inicio); const fim = Math.max(ini + 0.08, rel(p.fim))
    const prox = i + 1 < n ? rel(linha.palavras[i + 1].inicio) : duracao
    const chars = Array.from(w.querySelectorAll<HTMLElement>('.gs-char'))
    if (cfg.animacao === 'tipografica') {
      // cada palavra entra com stagger (o próprio tempo da fala), leve rotação e escala; a palavra falada fica laranja
      tl.fromTo(w, { opacity: 0, y: em * 0.45, rotation: -7, scale: 0.72 }, { opacity: 1, y: 0, rotation: 0, scale: 1, duration: 0.3, ease: 'back.out(1.9)' }, ini)
      tl.set(w, { color: cfg.cor_destaque }, ini)
      if (!p.enfase) tl.set(w, { color: cfg.cor_texto }, Math.max(ini + 0.05, prox))
    } else if (cfg.animacao === 'maquina') {
      // letras "digitadas" dentro do tempo da palavra; as não digitadas não ocupam espaço (o texto cresce como numa máquina)
      const passo = Math.max(0.012, (fim - ini) / Math.max(1, chars.length))
      chars.forEach((c, k) => tl.set(c, { display: 'inline-block' }, ini + k * passo))
      if (p.enfase) tl.set(w, { color: cfg.cor_destaque }, ini)
    } else {
      // onda: palavras entram subindo; na palavra de ênfase as letras sobem em onda, uma depois da outra
      tl.fromTo(w, { opacity: 0, y: em * 0.3 }, { opacity: 1, y: 0, duration: 0.22, ease: 'power2.out' }, ini)
      if (p.enfase) {
        tl.set(w, { color: cfg.cor_destaque }, ini)
        tl.to(chars, { y: -em * 0.32, duration: 0.16, ease: 'sine.inOut', yoyo: true, repeat: 1, stagger: 0.045 }, ini + 0.05)
      }
    }
    if (cfg.tremor && p.enfase) {
      // CustomWiggle: o x vai de 0 a 0,05 em e volta oscilando (o ease devolve -1..1 amortecendo); pulo de escala curto e discreto
      tl.to(w, { x: em * 0.05, rotation: 2, duration: 0.55, ease: 'gsTremor' }, ini)
      tl.fromTo(w, { scale: 1 }, { scale: 1.06, duration: 0.12, yoyo: true, repeat: 1, ease: 'power1.inOut' }, ini)
    }
  }
  if (cursor) tl.fromTo(cursor, { opacity: 1 }, { opacity: 0, duration: 0.3, repeat: -1, yoyo: true, ease: 'steps(1)' }, 0)
  return tl
}

const Linha = ({ cfg, linha, t, em }: { cfg: LegendaCineticaCfg; linha: LinhaLegenda; t: number; em: number }) => {
  const ref = useRef<HTMLDivElement>(null); const cursorRef = useRef<HTMLSpanElement>(null)
  const tl = useRef<gsap.core.Timeline | null>(null)
  const texto = useMemo(() => linha.palavras.map((p) => {
    const w = p.texto.replace(/\s+/g, ''); return escapar(cfg.maiusculas ? w.toUpperCase() : w)  // uma palavra do JSON = uma palavra do SplitText (sem espaço interno)
  }).join(' '), [linha, cfg.maiusculas])
  useLayoutEffect(() => {
    const el = ref.current; if (!el) return
    const split = new SplitText(el, { type: 'words,chars', wordsClass: 'gs-word', charsClass: 'gs-char' })
    gsap.set(split.words, { display: 'inline-block', transformOrigin: '50% 80%', whiteSpace: 'nowrap', margin: `0 ${em * 0.05}px` })  // folga para o tremor/escala não encostar na vizinha
    gsap.set(split.chars, { display: 'inline-block' })
    if (cfg.animacao === 'maquina') gsap.set(split.chars, { display: 'none' })
    tl.current = montarTimeline(cfg, linha, split, cursorRef.current, em)
    tl.current.seek(Math.max(0, t - linha.inicio), false)
    return () => { tl.current?.kill(); tl.current = null; split.revert() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg, linha, em])
  useLayoutEffect(() => { tl.current?.seek(Math.max(0, t - linha.inicio), false) }, [t, linha.inicio])
  const caixa: React.CSSProperties = cfg.caixa
    ? { background: cfg.cor_caixa || cfg.contorno, borderRadius: 20, padding: `${em * 0.22}px ${em * 0.5}px` }
    : { WebkitTextStroke: `${cfg.contorno_px}px ${cfg.contorno}`, paintOrder: 'stroke fill', textShadow: `0 ${Math.max(1, em * 0.04)}px ${em * 0.12}px rgba(0,0,0,0.45)` }
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: cfg.animacao === 'maquina' ? 'flex-start' : 'center', maxWidth: '88%', textAlign: cfg.animacao === 'maquina' ? 'left' : 'center',
      fontFamily: `${cfg.fonte}, Inter, sans-serif`, fontWeight: cfg.peso, fontSize: em, lineHeight: 1.18, color: cfg.cor_texto, ...caixa }}>
      <div ref={ref} dangerouslySetInnerHTML={{ __html: texto }} />
      {cfg.animacao === 'maquina' && <span ref={cursorRef} style={{ display: 'inline-block', width: em * 0.12, height: em * 0.9, marginLeft: em * 0.08, background: cfg.cor_destaque, borderRadius: 3, transform: 'translateY(12%)' }} />}
    </div>
  )
}

/** Legenda cinética: desenha a linha ativa no instante `t` (segundos do vídeo cortado). `oculta` some nos trechos de tela cheia. */
export const LegendaCinetica = ({ cfg, t, H, oculta }: { cfg: LegendaCineticaCfg; t: number; H: number; oculta?: boolean }) => {
  const i = cfg.linhas.findIndex((l) => t >= l.inicio && t < l.fim)
  if (i < 0 || oculta) return null
  const linha = cfg.linhas[i]; const em = cfg.tamanho
  const pos: React.CSSProperties = cfg.altura_pct != null
    ? { justifyContent: 'flex-end', paddingBottom: H * Math.max(2, Math.min(90, cfg.altura_pct)) / 100 }
    : cfg.posicao === 'alta' ? { justifyContent: 'flex-start', paddingTop: H * 0.22 }
    : cfg.posicao === 'centro' ? { justifyContent: 'center' }
    : { justifyContent: 'flex-end', paddingBottom: H * 0.12 }
  return (
    <AbsoluteFill style={{ alignItems: 'center', ...pos }}>
      <Linha key={`${i}-${linha.inicio}`} cfg={cfg} linha={linha} t={t} em={em} />
    </AbsoluteFill>
  )
}
