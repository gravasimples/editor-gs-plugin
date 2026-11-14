import { AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion'
import type { CenaTextoProps } from './tipos'

// Cena tipográfica animada para o vídeo do zero (montar_locucao): título palavra a palavra, barra laranja que cresce,
// linhas de apoio entrando uma a uma e um brilho laranja que anda devagar. Sem áudio: a narração vem da ferramenta.
const fontes = `
@font-face { font-family: 'InterGS'; font-weight: 800; src: url('${staticFile('fontes/Inter-ExtraBold.ttf')}') format('truetype'); }
@font-face { font-family: 'InterGS'; font-weight: 700; src: url('${staticFile('fontes/Inter-Bold.ttf')}') format('truetype'); }
@font-face { font-family: 'InterGS'; font-weight: 400; src: url('${staticFile('fontes/Inter-Regular.ttf')}') format('truetype'); }
`
const CORES = { papel: '#F2F2F2', grafite: '#272A33', nevoa: '#A7ACBD', laranja2: '#E9760D', azul: 'rgba(40,76,184,0.35)' }
const clamp = { extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const }
const suave = Easing.out(Easing.cubic)
const limpa = (s: string) => s.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '')

export const CenaTexto: React.FC<CenaTextoProps> = (p) => {
  const frame = useCurrentFrame()
  const { fps, width, height } = useVideoConfig()
  const t = frame / fps
  const claro = p.fundo === 'papel'
  const fundo = claro ? CORES.papel : p.estilo.cor_fundo
  const corTitulo = claro ? CORES.grafite : p.estilo.cor_texto
  const corApoio = claro ? CORES.grafite : CORES.nevoa
  const vertical = height > width
  const base = Math.min(width, height)
  const tamTitulo = base * (vertical ? 0.085 : 0.08)
  const tamApoio = base * 0.042
  const palavras = p.titulo.split(/\s+/).filter(Boolean)
  const animado = p.animacao !== 'nenhuma'
  const passo = p.animacao === 'palavras' ? 0.09 : 0
  const fimTitulo = 0.15 + palavras.length * passo + 0.35
  const escala = interpolate(t, [0, Math.max(0.5, p.duracao_s)], [1, 1.035], clamp)
  const opGeral = animado ? interpolate(t, [0, 0.3], [0, 1], clamp) : 1
  const barra = animado ? interpolate(t, [fimTitulo - 0.3, fimTitulo + 0.3], [0, 1], { ...clamp, easing: suave }) : 1
  const brilhoX = 50 + Math.sin(t * 0.5) * 12
  let destacou = false
  return (
    <AbsoluteFill style={{ backgroundColor: fundo, fontFamily: 'InterGS, Inter, sans-serif', justifyContent: 'center', padding: `0 ${width * 0.08}px` }}>
      <style>{fontes}</style>
      <AbsoluteFill style={{ background: `radial-gradient(circle at ${brilhoX}% ${vertical ? 80 : 88}%, rgba(247,150,21,${claro ? 0.1 : 0.16}) 0%, rgba(247,150,21,0) 45%)` }} />
      <div style={{ transform: `scale(${escala})`, transformOrigin: '0% 50%', opacity: opGeral }}>
        {p.selo && (
          <div style={{ display: 'inline-block', background: CORES.azul, borderRadius: 999, padding: `${tamApoio * 0.3}px ${tamApoio * 0.8}px`, color: claro ? CORES.grafite : '#FFFFFF',
            fontWeight: 700, fontSize: tamApoio * 0.8, marginBottom: tamTitulo * 0.5 }}>
            <span style={{ display: 'inline-block', width: tamApoio * 0.4, height: tamApoio * 0.4, borderRadius: 999, background: p.estilo.cor_destaque, marginRight: tamApoio * 0.4, verticalAlign: 'middle' }} />
            {p.selo}
          </div>
        )}
        <div style={{ fontWeight: 800, fontSize: tamTitulo, lineHeight: 1.1, color: corTitulo, letterSpacing: -0.5 }}>
          {palavras.map((w, i) => {
            const ini = 0.15 + i * passo
            const op = passo ? interpolate(t, [ini, ini + 0.28], [0, 1], { ...clamp, easing: suave }) : 1
            const dy = passo ? interpolate(t, [ini, ini + 0.28], [tamTitulo * 0.35, 0], { ...clamp, easing: suave }) : 0
            let cor = corTitulo
            if (p.destaque && !destacou && limpa(w) === limpa(p.destaque)) { cor = p.estilo.cor_destaque; destacou = true }
            return (
              <span key={i} style={{ display: 'inline-block', marginRight: tamTitulo * 0.28, opacity: op, transform: `translateY(${dy}px)`, color: cor }}>{w}</span>
            )
          })}
        </div>
        <div style={{ height: Math.max(4, tamTitulo * 0.08), width: `${barra * 18}%`, background: `linear-gradient(90deg, ${p.estilo.cor_destaque}, ${CORES.laranja2})`, borderRadius: 999,
          marginTop: tamTitulo * 0.35, marginBottom: p.apoio.length ? tamTitulo * 0.45 : 0 }} />
        {p.apoio.slice(0, 6).map((linha, i) => {
          const ini = fimTitulo + i * 0.18
          const op = animado ? interpolate(t, [ini, ini + 0.35], [0, 1], clamp) : 1
          const dx = animado ? interpolate(t, [ini, ini + 0.35], [-tamApoio * 0.6, 0], { ...clamp, easing: suave }) : 0
          return (
            <div key={i} style={{ fontWeight: 400, fontSize: tamApoio, lineHeight: 1.3, color: corApoio, opacity: op, transform: `translateX(${dx}px)`, marginBottom: tamApoio * 0.3 }}>
              {p.apoio.length > 1 ? '• ' : ''}{linha}
            </div>
          )
        })}
      </div>
    </AbsoluteFill>
  )
}
