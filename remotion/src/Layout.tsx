// Fase C (07/11/2026): layouts no jeito do Máquina (docs/maquina/ANALISE-2026-11-06.md, itens 13–17 e 21).
// O vídeo passa por blocos (cheio, painel, moldura, tutorial, tela, aula) normalizados em editor_video/layouts.py; a troca de bloco
// acontece por trás de uma cortina laranja. A tela (gravação do OBS) tem câmera virtual: focos aproximam e andam até o item, com contorno opcional.
import { AbsoluteFill, OffthreadVideo, interpolate, staticFile, Easing } from 'remotion'
import type { Bloco, Composto, Estilo, Foco, LayoutCfg } from './tipos'

const GRAD = (c: string) => `linear-gradient(90deg, ${c}, #E9760D)`
const suave = Easing.inOut(Easing.cubic)
export const PAINEL_FRAC = 0.34

export function blocoEm(t: number, blocos: Bloco[]): Bloco | null {
  if (!blocos.length) return null
  for (let i = blocos.length - 1; i >= 0; i--) if (t >= blocos[i].inicio) return blocos[i]
  return blocos[0]
}

// câmera virtual: chaves (t, zoom, x, y) montadas a partir dos focos; entre chaves, interpolação suave
type Cam = { z: number; x: number; y: number }
const REPOUSO: Cam = { z: 1, x: 0.5, y: 0.5 }
type Chave = Cam & { t: number }
function avaliar(chaves: Chave[], t: number): Cam {
  if (t <= chaves[0].t) return chaves[0]
  for (let i = 0; i < chaves.length - 1; i++) {
    const a = chaves[i], b = chaves[i + 1]
    if (t <= b.t) {
      const q = b.t > a.t ? suave((t - a.t) / (b.t - a.t)) : 1
      return { z: a.z + (b.z - a.z) * q, x: a.x + (b.x - a.x) * q, y: a.y + (b.y - a.y) * q }
    }
  }
  return chaves[chaves.length - 1]
}
export function camera(focos: Foco[], t: number): Cam {
  let chaves: Chave[] = [{ t: 0, ...REPOUSO }]
  for (const f of focos) {
    if (f.inicio > t + 1) break
    const atual = avaliar(chaves, f.inicio)
    chaves = chaves.filter(k => k.t < f.inicio)
    chaves.push({ t: f.inicio, ...atual }, { t: f.inicio + 0.55, z: f.zoom, x: f.x, y: f.y }, { t: Math.max(f.inicio + 0.55, f.fim), z: f.zoom, x: f.x, y: f.y }, { t: Math.max(f.inicio + 0.55, f.fim) + 0.55, ...REPOUSO })
  }
  return avaliar(chaves, t)
}

// posiciona a tela (tw×th) numa caixa (bw×bh): repouso = inteira (contain); zoom aproxima mantendo o ponto (x, y) no centro, sem sobrar borda
function enquadrar(tw: number, th: number, bw: number, bh: number, cam: Cam) {
  const s = Math.min(bw / tw, bh / th) * cam.z
  const w = tw * s, h = th * s
  const lim = (v: number, tam: number, caixa: number) => tam <= caixa ? (caixa - tam) / 2 : Math.min(0, Math.max(caixa - tam, v))
  return { left: lim(bw / 2 - cam.x * w, w, bw), top: lim(bh / 2 - cam.y * h, h, bh), w, h }
}

const TelaCam = ({ src, tw, th, bw, bh, focos, t, est, u, fundoBorrado }: { src: string; tw: number; th: number; bw: number; bh: number; focos: Foco[]; t: number; est: Estilo; u: number; fundoBorrado?: boolean }) => {
  const cam = camera(focos, t)
  const g = enquadrar(tw, th, bw, bh, cam)
  const ativo = focos.find(f => t >= f.inicio && t < f.fim && f.caixa)
  let contorno = null
  if (ativo && ativo.caixa) {
    const [cx, cy, cw, ch] = ativo.caixa
    const e = interpolate(t, [ativo.inicio + 0.45, ativo.inicio + 0.75], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(1.6)) })
    const sai = interpolate(t, [ativo.fim - 0.2, ativo.fim], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
    const pulso = 1 + 0.03 * Math.sin((t - ativo.inicio) * 7)
    const pad = 8 * u
    contorno = <div style={{ position: 'absolute', left: g.left + cx * g.w - pad, top: g.top + cy * g.h - pad, width: cw * g.w + 2 * pad, height: ch * g.h + 2 * pad,
      border: `${Math.max(4, 6 * u)}px solid ${est.cor_destaque}`, borderRadius: 18 * u, boxShadow: `0 0 ${24 * u}px rgba(247,150,21,0.65)`,
      opacity: Math.min(e, sai), transform: `scale(${(0.8 + 0.2 * e) * pulso})` }} />
  }
  return <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', background: est.cor_fundo }}>
    {fundoBorrado && <OffthreadVideo src={src} muted style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', filter: 'blur(26px) brightness(0.45)', transform: 'scale(1.1)' }} />}
    <OffthreadVideo src={src} muted style={{ position: 'absolute', left: g.left, top: g.top, width: g.w, height: g.h }} />
    {contorno}
  </div>
}

// barra de passos: o passo atual aceso (número + texto), os feitos com número laranja, os próximos apagados
export const BarraPassos = ({ passos, t, W, H, est }: { passos: { texto: string; inicio: number }[]; t: number; W: number; H: number; est: Estilo }) => {
  const vertical = H > W; const u = vertical ? W / 1080 : (H / 1080) * 0.85
  const atual = passos.reduce((k, p, i) => (t >= p.inicio ? i : k), -1)
  if (atual < 0 && t < passos[0].inicio - 0.3) return null
  const ent = interpolate(t, [passos[0].inicio - 0.3, passos[0].inicio], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) })
  const fs = 34 * u
  return <div style={{ position: 'absolute', top: H * (vertical ? 0.03 : 0.035), left: 0, right: 0, display: 'flex', justifyContent: 'center', opacity: ent, transform: `translateY(${(ent - 1) * 30 * u}px)` }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 * u, background: 'rgba(0,9,33,0.88)', border: '1.5px solid rgba(255,255,255,0.12)', borderRadius: 999, padding: `${10 * u}px ${12 * u}px`, maxWidth: '94%' }}>
      {passos.map((p, i) => {
        const aceso = i === atual; const feito = i < atual
        const troca = interpolate(t, [p.inicio, p.inicio + 0.3], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) })
        return <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 * u, borderRadius: 999, padding: aceso ? `${8 * u}px ${22 * u}px ${8 * u}px ${8 * u}px` : 0,
          background: aceso ? GRAD(est.cor_destaque) : 'transparent', opacity: aceso || feito ? 1 : 0.5, transform: aceso ? `scale(${0.9 + 0.1 * troca})` : undefined }}>
          <div style={{ width: fs * 1.35, height: fs * 1.35, borderRadius: 999, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: fs,
            background: aceso ? est.cor_fundo : feito ? est.cor_destaque : 'rgba(255,255,255,0.12)', color: aceso ? est.cor_destaque : feito ? est.cor_fundo : est.cor_texto }}>{i + 1}</div>
          {aceso && <div style={{ fontWeight: 800, fontSize: fs, color: est.cor_fundo, textTransform: 'uppercase', whiteSpace: 'nowrap', letterSpacing: 0.5 }}>{p.texto}</div>}
        </div>
      })}
    </div>
  </div>
}

// cortina laranja de quadro inteiro: cobre na primeira metade, revela na segunda (a troca de bloco acontece por trás dela)
export const Cortina = ({ instantes, t, est, dur = 0.5 }: { instantes: number[]; t: number; est: Estilo; dur?: number }) => {
  const c = instantes.find(x => t >= x - dur / 2 && t <= x + dur / 2)
  if (c === undefined) return null
  const q = (t - (c - dur / 2)) / dur
  const x = q < 0.5 ? interpolate(q, [0, 0.5], [-115, 0], { easing: Easing.out(Easing.cubic) }) : interpolate(q, [0.5, 1], [0, 115], { easing: Easing.in(Easing.cubic) })
  return <AbsoluteFill style={{ transform: `translateX(${x}%) skewX(-8deg)`, background: `linear-gradient(100deg, ${est.cor_destaque}, #E9760D)`, boxShadow: '0 0 60px rgba(0,0,0,0.4)' }}>
    <div style={{ position: 'absolute', top: 0, bottom: 0, left: '8%', width: '3%', background: est.cor_fundo, opacity: 0.9 }} />
  </AbsoluteFill>
}

// 09/11/2026: mostra numa caixa (bw×bh) só a faixa de linhas [y0, y1] (frações) do vídeo vw×vh. cover enquadra o foco (fx, fy, frações do quadro inteiro)
// a 45% da altura da caixa sem sair da faixa; contain deixa a faixa inteira dentro da caixa. A escala (punch-in) age sobre o foco.
const Recorte = ({ src, vw, vh, bw, bh, y0, y1, fx, fy, modo, escala = 1, muted, bg }: { src: string; vw: number; vh: number; bw: number; bh: number; y0: number; y1: number; fx: number; fy: number; modo: 'cover' | 'contain'; escala?: number; muted?: boolean; bg: string }) => {
  const rh = vh * (y1 - y0)
  const s = modo === 'cover' ? Math.max(bw / vw, bh / rh) : Math.min(bw / vw, bh / rh)
  const dw = vw * s, dh = vh * s
  const lim = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
  const left = dw > bw ? lim(bw / 2 - fx * dw, bw - dw, 0) : (bw - dw) / 2
  const top = modo === 'cover' ? lim(bh * 0.45 - fy * dh, bh - y1 * dh, -y0 * dh) : (bh - rh * s) / 2 - y0 * dh
  return <div style={{ position: 'absolute', left: 0, top: 0, width: bw, height: bh, overflow: 'hidden', background: bg }}>
    <div style={{ position: 'absolute', left, top, width: dw, height: dh, clipPath: `inset(${y0 * dh}px 0 ${dh - y1 * dh}px 0)`, transform: `scale(${escala})`, transformOrigin: `${(fx * 100).toFixed(1)}% ${(fy * 100).toFixed(1)}%` }}>
      <OffthreadVideo src={src} muted={muted} style={{ width: '100%', height: '100%' }} />
    </div>
  </div>
}

export function trechoComposto(t: number, c: Composto): boolean {
  const tr = c.trechos.find(x => t >= x.inicio && t < x.fim) ?? c.trechos[c.trechos.length - 1]
  return !!tr && tr.composto
}
export const COLUNA_TELA = 0.64
// fração da largura que vira painel marinho para os grafismos: só no composto horizontal, nos trechos em que o bruto mostra só o rosto
export function colunaEsquerda(cfg: LayoutCfg | null, t: number, vertical: boolean): number {
  if (!cfg || vertical || !cfg.composto) return 0
  const b = blocoEm(t, cfg.blocos)
  return b && b.modo === 'composto' && !trechoComposto(t, cfg.composto) ? COLUNA_TELA : 0
}

// camada de vídeo com layout: o vídeo principal (rosto, com o áudio) fica sempre montado; a tela e o rosto recortado entram quando o bloco pede
export const CamadaLayout = ({ cfg, video, t, W, H, escala, est, mudaOrientacao }: { cfg: LayoutCfg; video: string; t: number; W: number; H: number; escala: number; est: Estilo; mudaOrientacao?: boolean }) => {
  const b = blocoEm(t, cfg.blocos)
  const modo = b ? b.modo : 'cheio'
  const vertical = H > W; const u = vertical ? W / 1080 : (H / 1080) * 0.85
  const srcRosto = staticFile(`render/${video}`)
  const srcTela = cfg.tela ? staticFile(`render/${cfg.tela}`) : ''
  const tw = cfg.tela_largura || 1920, th = cfg.tela_altura || 1080
  const focos = cfg.focos || []
  // com rosto_pos, o objectPosition põe o rosto no centro da largura e a ~40% da altura da caixa (cover); sem ele, o enquadramento padrão
  const posRosto = (bw: number, bh: number, pad: string) => {
    const rp = cfg.rosto_pos, vw = cfg.rosto_largura, vh = cfg.rosto_altura
    if (!rp || !vw || !vh) return pad
    const s = Math.max(bw / vw, bh / vh), iw = vw * s, ih = vh * s
    const c = (v: number) => Math.min(1, Math.max(0, v))
    const px = iw - bw > 1 ? c((0.5 * bw - rp.x * iw) / (bw - iw)) : 0.5
    const py = ih - bh > 1 ? c((0.4 * bh - rp.y * ih) / (bh - ih)) : 0.5
    return `${(px * 100).toFixed(1)}% ${(py * 100).toFixed(1)}%`
  }
  const rostoCaixa = (box: React.CSSProperties, pos = '50% 35%', extra?: React.CSSProperties) => (
    <div style={{ position: 'absolute', overflow: 'hidden', ...box, ...extra }}>
      <OffthreadVideo src={srcRosto} style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: posRosto(Number(box.width), Number(box.height), pos), transform: `scale(${escala})`, transformOrigin: '50% 40%' }} />
    </div>
  )
  const fundoMarinho = <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 30%, rgba(247,150,21,0.14), rgba(0,9,33,0) 50%), ${est.cor_fundo}` }} />
  // composto (09/11): bruto vertical com a tela em cima e o rosto embaixo. Na saída horizontal, trecho composto = tela à esquerda (64%, inteira) e rosto à
  // direita (cover no rosto); trecho só de rosto = close no rosto (cover). Na saída vertical o bruto já está composto: cai no 'cheio'.
  if (modo === 'composto' && cfg.composto && !vertical && cfg.rosto_largura && cfg.rosto_altura) {
    const c = cfg.composto, vw = cfg.rosto_largura, vh = cfg.rosto_altura
    const comp = trechoComposto(t, c)
    const rb = c.rosto_baixo || { x: 0.5, y: 0.78 }, rc = c.rosto_cima || { x: 0.5, y: 0.4 }
    const wt = Math.round(W * COLUNA_TELA), div = Math.min(0.9, c.divisor + 0.02)
    // o rosto fica sempre na coluna da direita (não pula de lugar); trecho só de rosto = plano médio do quadro inteiro e painel marinho à esquerda (grafismos)
    if (!comp) {
      return <AbsoluteFill style={{ background: est.cor_fundo }}>
        {fundoMarinho}
        <div style={{ position: 'absolute', left: wt, top: 0, width: W - wt, height: H }}>
          <Recorte src={srcRosto} vw={vw} vh={vh} bw={W - wt} bh={H} y0={0} y1={1} fx={rc.x} fy={rc.y} modo="cover" escala={escala} bg={est.cor_fundo} />
        </div>
        <div style={{ position: 'absolute', top: 0, left: wt - 3 * u, height: H, width: Math.max(4, 6 * u), background: GRAD(est.cor_destaque) }} />
      </AbsoluteFill>
    }
    return <AbsoluteFill style={{ background: est.cor_fundo }}>
      <div style={{ position: 'absolute', left: 0, top: 0, width: wt, height: H }}>
        <Recorte src={srcRosto} vw={vw} vh={vh} bw={wt} bh={H} y0={0} y1={c.divisor} fx={0.5} fy={c.divisor / 2} modo="contain" muted bg={est.cor_fundo} />
      </div>
      <div style={{ position: 'absolute', left: wt, top: 0, width: W - wt, height: H }}>
        <Recorte src={srcRosto} vw={vw} vh={vh} bw={W - wt} bh={H} y0={div} y1={1} fx={rb.x} fy={rb.y} modo="cover" escala={escala} bg={est.cor_fundo} />
      </div>
      <div style={{ position: 'absolute', top: 0, left: wt - 3 * u, height: H, width: Math.max(4, 6 * u), background: GRAD(est.cor_destaque) }} />
    </AbsoluteFill>
  }
  if (modo === 'painel') {
    const ph = H * (vertical ? PAINEL_FRAC : 0.3)
    return <AbsoluteFill>
      {fundoMarinho}
      {rostoCaixa({ left: 0, top: ph, width: W, height: H - ph }, '50% 30%')}
      <div style={{ position: 'absolute', left: 0, top: ph - 3 * u, width: W, height: Math.max(4, 6 * u), background: GRAD(est.cor_destaque) }} />
    </AbsoluteFill>
  }
  if (modo === 'moldura') {
    const box = vertical ? { left: W * 0.06, top: H * 0.07, width: W * 0.88, height: H * 0.74 } : { left: W * 0.17, top: H * 0.08, width: W * 0.66, height: H * 0.8 }
    return <AbsoluteFill>
      {fundoMarinho}
      {rostoCaixa(box, '50% 35%', { borderRadius: 40 * u, border: `${Math.max(4, 7 * u)}px solid ${est.cor_destaque}`, boxShadow: `0 ${18 * u}px ${60 * u}px rgba(0,0,0,0.5), 0 0 ${40 * u}px rgba(247,150,21,0.25)` })}
    </AbsoluteFill>
  }
  if (modo === 'tutorial' && srcTela) {
    const telaBox = vertical ? { left: 0, top: 0, width: W, height: H * 0.5 } : { left: 0, top: 0, width: W * 0.64, height: H }
    const rostoBox = vertical ? { left: 0, top: H * 0.5, width: W, height: H * 0.5 } : { left: W * 0.64, top: 0, width: W * 0.36, height: H }
    return <AbsoluteFill style={{ background: est.cor_fundo }}>
      <div style={{ position: 'absolute', ...telaBox }}><TelaCam src={srcTela} tw={tw} th={th} bw={telaBox.width} bh={telaBox.height} focos={focos} t={t} est={est} u={u} /></div>
      {rostoCaixa(rostoBox, '50% 30%')}
      <div style={vertical ? { position: 'absolute', left: 0, top: H * 0.5 - 3 * u, width: W, height: Math.max(4, 6 * u), background: GRAD(est.cor_destaque) }
        : { position: 'absolute', top: 0, left: W * 0.64 - 3 * u, height: H, width: Math.max(4, 6 * u), background: est.cor_destaque }} />
    </AbsoluteFill>
  }
  if ((modo === 'tela' || modo === 'aula') && srcTela) {
    const rec = modo === 'aula' && cfg.rosto_recortado ? staticFile(`render/${cfg.rosto_recortado}`) : ''
    const bolha = modo === 'aula' && !rec
    const d = Math.min(W, H) * 0.3
    return <AbsoluteFill style={{ background: est.cor_fundo }}>
      <TelaCam src={srcTela} tw={tw} th={th} bw={W} bh={H} focos={focos} t={t} est={est} u={u} fundoBorrado={vertical} />
      {/* o vídeo do rosto continua montado (é ele que leva o áudio); só aparece na bolha */}
      {bolha ? rostoCaixa({ right: W * 0.03, bottom: H * (vertical ? 0.2 : 0.05), width: d, height: d }, '50% 30%', { borderRadius: 999, border: `${Math.max(4, 6 * u)}px solid ${est.cor_destaque}`, boxShadow: '0 10px 40px rgba(0,0,0,0.5)' })
        : <OffthreadVideo src={srcRosto} style={{ position: 'absolute', width: 2, height: 2, opacity: 0 }} />}
      {rec && <OffthreadVideo src={rec} muted transparent style={vertical ? { position: 'absolute', left: '50%', bottom: 0, height: H * 0.42, transform: 'translateX(-50%)' }
        : { position: 'absolute', right: W * 0.01, bottom: 0, height: H * 0.48 }} />}
    </AbsoluteFill>
  }
  return <AbsoluteFill style={{ transform: `scale(${escala})`, transformOrigin: '50% 45%' }}>
    <OffthreadVideo src={srcRosto} style={{ width: '100%', height: '100%', objectFit: mudaOrientacao ? 'contain' : 'cover' }} />
  </AbsoluteFill>
}
