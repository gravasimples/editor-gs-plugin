// Fase E (08/11/2026): câmera do vídeo cortado, a partir dos planos de editor_video/transicoes.py.
// Cada plano anda devagar (z0 → z1) e entra com o tratamento escolhido: seco, punch, tremor, zoom_blur, deslize, giro, luz ou flash.
// As fortes atravessam a emenda: metade da duração no fim do plano anterior (saída) e metade no começo do novo (entrada).
import { AbsoluteFill, interpolate, Easing } from 'remotion'
import type { Plano } from './tipos'

export type EstadoCamera = { escala: number; tx: number; ty: number; rot: number; blur: number; luz: number; luzX: number; flash: number }

const sai = (x: number) => Easing.in(Easing.cubic)(Math.min(1, Math.max(0, x)))
const entra = (x: number) => Easing.out(Easing.cubic)(Math.min(1, Math.max(0, x)))
const FORTES = ['zoom_blur', 'deslize', 'giro', 'luz', 'flash']

export function camera(t: number, planos: Plano[], W: number): EstadoCamera {
  const e: EstadoCamera = { escala: 1, tx: 0, ty: 0, rot: 0, blur: 0, luz: 0, luzX: 0, flash: 0 }
  if (!planos.length) return e
  let i = planos.findIndex((p) => t >= p.inicio && t < p.fim)
  if (i < 0) i = t < planos[0].inicio ? 0 : planos.length - 1
  const p = planos[i]
  const dur = Math.max(0.001, p.fim - p.inicio)
  e.escala = interpolate(t, [p.inicio, p.fim], [p.z0, p.z1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.sin) })
  const lado = i % 2 === 0 ? 1 : -1
  // entrada do plano atual
  const tl = t - p.inicio; const d = Math.max(0.05, p.dur); const k = p.intensidade || 1
  const meia = FORTES.includes(p.entrada) ? d / 2 : d
  const x = tl / meia; const resto = 1 - entra(x)   // 1 no corte, 0 no fim da entrada
  if (tl >= 0 && tl < meia) {
    switch (p.entrada) {
      case 'punch': e.escala *= 1 + 0.035 * k * resto; break
      case 'tremor': { const a = 14 * k * resto * (W / 1080); e.tx += Math.sin(tl * 95) * a; e.ty += Math.cos(tl * 77) * a * 0.7; e.rot += Math.sin(tl * 60) * 0.8 * resto; e.escala *= 1 + 0.05 * resto; break }
      case 'zoom_blur': e.escala *= 1 + 0.28 * k * resto; e.blur += 16 * resto; break
      case 'deslize': e.tx += lado * 0.07 * W * resto; e.blur += 18 * resto; e.escala *= 1 + 0.15 * resto; break
      case 'giro': e.rot += lado * 7 * k * resto; e.escala *= 1 + 0.26 * resto; e.blur += 8 * resto; break
      case 'flash': e.flash = Math.max(e.flash, 0.85 * resto); break
    }
  }
  // saída rumo ao próximo plano (as fortes começam antes da emenda)
  const q = planos[i + 1]
  if (q && FORTES.includes(q.entrada)) {
    const m = Math.max(0.05, q.dur) / 2; const ts = q.inicio - t
    if (ts >= 0 && ts < m) {
      const y = sai(1 - ts / m); const kq = q.intensidade || 1   // 0 longe da emenda, 1 na emenda
      const ladoQ = (i + 1) % 2 === 0 ? 1 : -1
      switch (q.entrada) {
        case 'zoom_blur': e.escala *= 1 + 0.22 * kq * y; e.blur += 14 * y; break
        case 'deslize': e.tx -= ladoQ * 0.07 * W * y; e.blur += 18 * y; e.escala *= 1 + 0.15 * y; break
        case 'giro': e.rot -= ladoQ * 6 * kq * y; e.escala *= 1 + 0.24 * y; e.blur += 6 * y; break
        case 'flash': e.flash = Math.max(e.flash, 0.5 * y); break
      }
    }
  }
  // luz laranja atravessando a emenda (antes e depois)
  for (const r of [p, q]) {
    if (!r || r.entrada !== 'luz') continue
    const d2 = Math.max(0.2, r.dur); const rel = (t - (r.inicio - d2 * 0.45)) / d2
    if (rel >= 0 && rel <= 1) { e.luz = Math.max(e.luz, Math.sin(Math.PI * rel) * 0.75 * (r.intensidade || 1)); e.luzX = rel }
  }
  return e
}

export const transformCamera = (c: EstadoCamera) => `translate(${c.tx}px, ${c.ty}px) rotate(${c.rot}deg) scale(${c.escala})`
export const filtroCamera = (c: EstadoCamera) => (c.blur > 0.3 ? `blur(${c.blur.toFixed(1)}px)` : undefined)

export const LuzCamera = ({ c, cor }: { c: EstadoCamera; cor: string }) => {
  if (c.luz <= 0.01 && c.flash <= 0.01) return null
  return <>
    {c.luz > 0.01 && <AbsoluteFill style={{ mixBlendMode: 'screen', opacity: c.luz,
      background: `linear-gradient(105deg, rgba(0,0,0,0) ${-40 + c.luzX * 120}%, ${cor} ${-15 + c.luzX * 120}%, #FFD9A0 ${-5 + c.luzX * 120}%, ${cor} ${5 + c.luzX * 120}%, rgba(0,0,0,0) ${30 + c.luzX * 120}%)` }} />}
    {c.flash > 0.01 && <AbsoluteFill style={{ backgroundColor: 'white', opacity: c.flash }} />}
  </>
}
