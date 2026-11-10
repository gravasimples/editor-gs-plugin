// Fase B (07/11/2026): camada de grafismos semânticos, no jeito do Máquina (docs/maquina/referencias/*.jpg).
// Cada item do plano (grafismos.json, normalizado em editor_video/grafismos.py) entra na palavra, dura o tempo da ideia e some.
// Zonas: topo (kicker, cartões), peito (entre o rosto e a legenda) e centro (tela cheia: fundo marinho cobre o vídeo, legenda some).
import { AbsoluteFill, Img, interpolate, spring, staticFile, Easing } from 'remotion'
import type { Estilo, Grafismo, Midia } from './tipos'

const GRAD = (c: string) => `linear-gradient(90deg, ${c}, #E9760D)`
const SOMBRA = '0 4px 18px rgba(0,0,0,0.55)'
const CARD = '#0B193D'

type Ctx = { t: number; fps: number; u: number; W: number; H: number; vertical: boolean; est: Estilo }

const mola = (tl: number, fps: number, damping = 14) => tl < 0 ? 0 : spring({ frame: Math.round(tl * fps), fps, config: { damping, stiffness: 170, mass: 0.6 } })
const rampa = (t: number, a: number, b: number) => interpolate(t, [a, b], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) })

function svgCheio(svg: string) {
  return svg.replace(/\s(width|height)="[^"]*"/g, '').replace(/<svg/, '<svg width="100%" height="100%"')
}

const MidiaView = ({ m, tam, cor, raio = 16, fundoMarca = true }: { m?: Midia; tam: number; cor: string; raio?: number; fundoMarca?: boolean }) => {
  if (!m) return null
  if (m.tipo === 'img' && m.arquivo) return <Img src={staticFile(`render/${m.arquivo}`)} style={{ width: tam, height: tam, objectFit: 'cover', borderRadius: raio }} />
  if (m.tipo === 'svg' && m.svg) {
    const marca = !!m.marca
    const inner = <div style={{ width: marca ? tam * 0.62 : tam * 0.56, height: marca ? tam * 0.62 : tam * 0.56, fill: marca ? m.cor : 'none', color: marca ? m.cor : cor }} dangerouslySetInnerHTML={{ __html: svgCheio(m.svg) }} />
    if (marca && fundoMarca) return <div style={{ width: tam, height: tam, borderRadius: raio * 1.2, background: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 24px rgba(0,0,0,0.35)' }}>{inner}</div>
    return <div style={{ width: tam, height: tam, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{inner}</div>
  }
  return null
}

const Check = ({ tam, cor, fundo }: { tam: number; cor: string; fundo: string }) => (
  <div style={{ width: tam, height: tam, borderRadius: 999, background: GRAD(cor), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
    <svg width={tam * 0.62} height={tam * 0.62} viewBox="0 0 24 24" fill="none" stroke={fundo} strokeWidth={3.4} strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
  </div>
)

// palavras entrando uma a uma; a(s) palavra(s) do destaque ficam laranja (ou numa caixa laranja)
const Palavras = ({ texto, destaque, c, tl, passo = 0.07, caixa = false }: { texto: string; destaque?: string; c: Ctx; tl: number; passo?: number; caixa?: boolean }) => {
  const limpa = (w: string) => w.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[.,!?:;"'…]/g, '')
  const alvo = (destaque || '').split(/\s+/).map(limpa).filter(Boolean)
  return <>{texto.split(/\s+/).filter(Boolean).map((w, i) => {
    const e = mola(tl - i * passo, c.fps, 12)
    const d = alvo.includes(limpa(w))
    const estiloCaixa = d && caixa ? { background: GRAD(c.est.cor_destaque), color: c.est.cor_fundo, padding: `0 ${0.18}em`, borderRadius: '0.16em', textShadow: 'none' } : {}
    return <span key={i} style={{ display: 'inline-block', opacity: Math.min(1, e), transform: `translateY(${(1 - e) * 22}px) scale(${0.75 + 0.25 * e})`, color: d && !caixa ? c.est.cor_destaque : undefined, marginRight: '0.24em', ...estiloCaixa }}>{w}</span>
  })}</>
}

const Pilula = ({ texto, c, tam, laranja = true, ponto = false }: { texto: string; c: Ctx; tam: number; laranja?: boolean; ponto?: boolean }) => (
  <div style={{ display: 'inline-flex', alignItems: 'center', gap: tam * 0.4, background: laranja ? GRAD(c.est.cor_destaque) : 'rgba(11,25,61,0.92)', color: laranja ? c.est.cor_fundo : c.est.cor_texto,
    border: laranja ? 'none' : '1.5px solid rgba(255,255,255,0.14)', fontWeight: 800, fontSize: tam, lineHeight: 1, padding: `${tam * 0.42}px ${tam * 0.8}px`, borderRadius: 999,
    textTransform: 'uppercase', letterSpacing: tam * 0.05, boxShadow: '0 8px 26px rgba(0,0,0,0.35)', whiteSpace: 'nowrap' }}>
    {ponto && <div style={{ width: tam * 0.42, height: tam * 0.42, borderRadius: 999, background: c.est.cor_destaque }} />}{texto}
  </div>
)

function Conteudo({ g, c }: { g: Grafismo; c: Ctx }) {
  const { u, est } = c; const tl = c.t - g.inicio
  const em = (x?: number) => c.t - (x ?? g.inicio)
  switch (g.tipo) {
    case 'kicker':
      return <Pilula texto={g.texto || ''} c={c} tam={30 * u} laranja={false} ponto />
    case 'serie':
      return <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 * u }}>
        <div style={{ opacity: mola(tl, c.fps), transform: `scale(${0.8 + 0.2 * mola(tl, c.fps)})` }}><Pilula texto={g.parte ? `Parte ${g.parte}` : (g.kicker || '')} c={c} tam={26 * u} laranja={false} ponto /></div>
        <div style={{ fontWeight: 800, fontSize: 84 * u, lineHeight: 1.02, color: est.cor_texto, textTransform: 'uppercase', textAlign: 'center', textShadow: SOMBRA, maxWidth: c.W * 0.9 }}>
          <Palavras texto={g.texto || ''} destaque={g.destaque} c={c} tl={tl - 0.15} passo={0.16} />
        </div>
      </div>
    case 'manchete':
      return <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 * u, maxWidth: c.W * 0.9 }}>
        {g.rotulo && <div style={{ opacity: mola(tl, c.fps), transform: `translateY(${(1 - mola(tl, c.fps)) * 14}px)` }}><Pilula texto={g.rotulo} c={c} tam={26 * u} /></div>}
        <div style={{ fontWeight: 800, fontSize: (g.tela_cheia ? 104 : 80) * u, lineHeight: 1.08, color: est.cor_texto, textTransform: 'uppercase', textAlign: 'center', textShadow: g.caixa ? 'none' : SOMBRA }}>
          <Palavras texto={g.texto || ''} destaque={g.destaque} c={c} tl={tl - (g.rotulo ? 0.12 : 0)} caixa={!!g.caixa} />
        </div>
        {g.ondas && <Ondas c={c} tl={tl} largura={c.W * 0.62} altura={70 * u} />}
      </div>
    case 'pilula': {
      const e = mola(tl, c.fps, 11)
      return <div style={{ transform: `scale(${0.6 + 0.4 * e}) rotate(${(1 - e) * -3}deg)`, opacity: Math.min(1, e * 1.5) }}><Pilula texto={g.texto || ''} c={c} tam={46 * u} /></div>
    }
    case 'riscado': {
      const linha = rampa(tl, 0.25, 0.6); const tt = g.troca_em != null ? c.t - g.troca_em : tl - 1.0; const et = mola(tt, c.fps, 11)
      return <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 * u }}>
        <div style={{ position: 'relative', fontWeight: 800, fontSize: 60 * u, color: est.cor_texto, textTransform: 'uppercase', textShadow: SOMBRA, opacity: 1 - 0.4 * linha }}>
          {g.texto}
          <div style={{ position: 'absolute', left: '-4%', top: '52%', height: 9 * u, width: `${linha * 108}%`, background: GRAD(est.cor_destaque), borderRadius: 999, transform: 'rotate(-3deg)', boxShadow: '0 2px 8px rgba(0,0,0,0.4)' }} />
        </div>
        {g.troca && tt >= 0 && <div style={{ transform: `scale(${0.6 + 0.4 * et})`, opacity: Math.min(1, et * 1.5) }}><Pilula texto={g.troca} c={c} tam={44 * u} /></div>}
      </div>
    }
    case 'checklist':
      return <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 14 * u }}>
        {(g.itens || []).map((it, i) => {
          const e = mola(em(it.em), c.fps); if (em(it.em) < 0) return null
          return <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 16 * u, background: 'rgba(0,9,33,0.8)', borderRadius: 999, padding: `${10 * u}px ${28 * u}px ${10 * u}px ${10 * u}px`,
            opacity: Math.min(1, e * 1.4), transform: `translateX(${(1 - e) * -40}px)` }}>
            <Check tam={46 * u} cor={est.cor_destaque} fundo={est.cor_fundo} />
            <div style={{ fontWeight: 800, fontSize: 36 * u, color: est.cor_texto, textTransform: 'uppercase' }}>{it.texto}</div>
          </div>
        })}
      </div>
    case 'pilulas':
      return <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 14 * u, maxWidth: c.W * 0.9 }}>
        {(g.itens || []).map((it, i) => {
          const tt = em(it.em); if (tt < 0) return null; const e = mola(tt, c.fps, 11)
          const ultimo = (g.itens || []).filter(x => em(x.em) >= 0).length - 1 === i
          return <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 * u, background: ultimo ? GRAD(est.cor_destaque) : 'rgba(11,25,61,0.92)', color: ultimo ? est.cor_fundo : est.cor_texto,
            border: ultimo ? 'none' : '1.5px solid rgba(255,255,255,0.14)', borderRadius: 999, padding: `${12 * u}px ${26 * u}px ${12 * u}px ${it.midia ? 12 * u : 26 * u}px`,
            fontWeight: 800, fontSize: 36 * u, textTransform: 'uppercase', transform: `scale(${0.6 + 0.4 * e})`, opacity: Math.min(1, e * 1.5) }}>
            {it.midia && <MidiaView m={it.midia} tam={48 * u} cor={est.cor_texto} raio={10 * u} />}{it.texto}
          </div>
        })}
      </div>
    case 'fluxo': {
      const its = g.itens || []; const tam = 116 * u
      return <div style={{ display: 'flex', alignItems: 'flex-start' }}>
        {its.map((it, i) => {
          const tt = em(it.em); const e = mola(tt, c.fps, 11); const vis = tt >= 0
          const proxima = its[i + 1]; const lin = proxima ? rampa(em(proxima.em), -0.05, 0.25) : 0
          const atual = vis && (!proxima || em(proxima.em) < 0)
          return <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 * u, opacity: vis ? Math.min(1, e * 1.5) : 0, transform: `scale(${0.5 + 0.5 * e})` }}>
              <div style={{ width: tam, height: tam, borderRadius: 26 * u, background: atual ? GRAD(est.cor_destaque) : CARD, border: atual ? 'none' : '2px solid rgba(255,255,255,0.16)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 10px 30px rgba(0,0,0,0.4)' }}>
                <MidiaView m={it.midia} tam={tam * 0.9} cor={atual ? est.cor_fundo : est.cor_texto} fundoMarca={false} />
              </div>
              {it.texto && <div style={{ fontWeight: 800, fontSize: 26 * u, color: est.cor_texto, textTransform: 'uppercase', textShadow: SOMBRA }}>{it.texto}</div>}
            </div>
            {proxima && <div style={{ width: 90 * u, height: 7 * u, marginTop: -(it.texto ? 36 * u : 0), background: 'rgba(255,255,255,0.12)', borderRadius: 999, overflow: 'hidden' }}>
              <div style={{ width: `${lin * 100}%`, height: '100%', background: GRAD(est.cor_destaque) }} /></div>}
          </div>
        })}
      </div>
    }
    case 'cartoes':
      return <div style={{ display: 'flex', gap: 28 * u, justifyContent: 'center' }}>
        {(g.itens || []).map((it, i) => {
          const tt = em(it.em); if (tt < 0) return null; const e = mola(tt, c.fps)
          const ok = it.sinal !== 'nao'
          return <div key={i} style={{ width: (g.itens!.length > 1 ? 420 : 520) * u, background: CARD, borderRadius: 22 * u, border: `2px solid ${ok ? 'rgba(255,255,255,0.16)' : est.cor_destaque}`,
            padding: 22 * u, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 * u, boxShadow: '0 14px 40px rgba(0,0,0,0.45)', opacity: Math.min(1, e * 1.4), transform: `translateY(${(1 - e) * -30}px) scale(${0.85 + 0.15 * e})` }}>
            {it.rotulo && <div style={{ fontWeight: 800, fontSize: 30 * u, color: est.cor_texto, textTransform: 'uppercase', letterSpacing: 1 }}>{it.rotulo}</div>}
            {it.midia ? (it.midia.tipo === 'img' ? <Img src={staticFile(`render/${it.midia.arquivo}`)} style={{ width: '100%', height: 190 * u, objectFit: 'cover', borderRadius: 14 * u }} />
              : <MidiaView m={it.midia} tam={150 * u} cor={est.cor_destaque} />) : null}
            {(it.texto || it.sinal) && <div style={{ display: 'flex', alignItems: 'center', gap: 10 * u, fontWeight: 800, fontSize: 32 * u, color: ok ? est.cor_texto : est.cor_destaque, textTransform: 'uppercase' }}>
              <span style={{ color: est.cor_destaque }}>{ok ? '✓' : '✕'}</span>{it.texto}</div>}
          </div>
        })}
      </div>
    case 'numero': {
      const e = mola(tl - (g.antes?.length ? 0.35 : 0), c.fps, 11)
      return <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 * u }}>
        {g.midia && <div style={{ opacity: mola(tl, c.fps), marginBottom: 10 * u }}><MidiaView m={g.midia} tam={(g.tela_cheia ? 300 : 170) * u} cor={est.cor_destaque} raio={22 * u} /></div>}
        {(g.antes || []).map((a, i) => {
          const tt = em(a.em); if (tt < 0) return null
          return <div key={i} style={{ fontWeight: 800, fontSize: 76 * u, lineHeight: 1.05, color: 'rgba(255,255,255,0.45)', opacity: rampa(tt, 0, 0.25), textDecoration: 'line-through', textDecorationColor: est.cor_destaque }}>{a.texto}</div>
        })}
        {g.rotulo && <div style={{ fontWeight: 800, fontSize: 40 * u, color: est.cor_texto, textTransform: 'uppercase', textShadow: SOMBRA, opacity: e }}>{g.rotulo}</div>}
        <div style={{ fontWeight: 800, fontSize: (g.tela_cheia ? 190 : 150) * u, lineHeight: 1, background: GRAD(est.cor_destaque), WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
          filter: 'drop-shadow(0 6px 18px rgba(0,0,0,0.45))', transform: `scale(${0.5 + 0.5 * e})`, opacity: Math.min(1, e * 1.4) }}>{g.texto}</div>
        {g.sub && <div style={{ fontWeight: 800, fontSize: 30 * u, color: est.cor_texto, letterSpacing: 2 * u, textTransform: 'uppercase', textShadow: SOMBRA, opacity: rampa(tl, 0.5, 0.8) }}>{g.sub}</div>}
      </div>
    }
    case 'logos':
      return <div style={{ display: 'flex', gap: 26 * u, justifyContent: 'center', alignItems: 'flex-start' }}>
        {(g.itens || []).map((it, i) => {
          const tt = em(it.em); if (tt < 0) return null; const e = mola(tt, c.fps, 10)
          return <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 * u, transform: `scale(${0.4 + 0.6 * e}) translateY(${(1 - e) * 30}px)`, opacity: Math.min(1, e * 1.6) }}>
            <MidiaView m={it.midia} tam={150 * u} cor={est.cor_destaque} raio={26 * u} />
            {it.texto && <div style={{ fontWeight: 800, fontSize: 28 * u, color: est.cor_texto, textTransform: 'uppercase', textShadow: SOMBRA }}>{it.texto}</div>}
          </div>
        })}
      </div>
    case 'ondas':
      return <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 * u }}>
        {g.texto && <div style={{ fontWeight: 800, fontSize: 64 * u, color: est.cor_texto, textTransform: 'uppercase', textShadow: SOMBRA }}><Palavras texto={g.texto} destaque={g.destaque} c={c} tl={tl} /></div>}
        <Ondas c={c} tl={tl} largura={c.W * 0.7} altura={110 * u} />
      </div>
    case 'cta': {
      const e = mola(tl, c.fps); const seguindo = tl > (g.fim - g.inicio) * 0.55
      return <div style={{ display: 'flex', alignItems: 'center', gap: 22 * u, background: 'rgba(0,9,33,0.88)', border: '1.5px solid rgba(255,255,255,0.14)', borderRadius: 28 * u,
        padding: `${18 * u}px ${20 * u}px ${18 * u}px ${30 * u}px`, transform: `translateY(${(1 - e) * 40}px)`, opacity: Math.min(1, e * 1.4), boxShadow: '0 12px 36px rgba(0,0,0,0.45)' }}>
        <div>
          <div style={{ fontWeight: 800, fontSize: 38 * u, color: est.cor_texto }}>{g.handle || '@thiago.obsstudio'}</div>
          {g.texto && <div style={{ fontWeight: 400, fontSize: 24 * u, color: '#A7ACBD', marginTop: 4 * u }}>{g.texto}</div>}
        </div>
        <div style={{ background: seguindo ? CARD : GRAD(est.cor_destaque), color: seguindo ? est.cor_texto : est.cor_fundo, border: seguindo ? '1.5px solid rgba(255,255,255,0.2)' : 'none',
          fontWeight: 800, fontSize: 30 * u, borderRadius: 999, padding: `${12 * u}px ${30 * u}px` }}>{seguindo ? '✓ Seguindo' : (g.botao || 'Seguir')}</div>
      </div>
    }
  }
  return null
}

export const Ondas = ({ c, tl, largura, altura }: { c: Ctx; tl: number; largura: number; altura: number }) => {
  const n = 38; const ent = rampa(tl, 0, 0.4)
  return <div style={{ display: 'flex', alignItems: 'center', gap: largura / n * 0.35, height: altura }}>
    {Array.from({ length: n }).map((_, i) => {
      const meio = 1 - Math.abs(i - n / 2) / (n / 2)
      const h = (0.18 + 0.82 * meio * (0.55 + 0.45 * Math.sin(tl * 9 + i * 0.85) * Math.cos(tl * 4.3 + i * 0.37))) * ent
      return <div key={i} style={{ width: largura / n * 0.65, height: Math.max(4, altura * Math.abs(h)), borderRadius: 999, background: GRAD(c.est.cor_destaque) }} />
    })}
  </div>
}

// Fase E (08/11/2026): repertório de entrada e saída por item (grafismos.variar_animacoes distribui sem repetir em seguida).
// "mola" é a entrada antiga (só a mola interna das palavras); as outras somam um movimento do bloco inteiro.
type Mov = { transform?: string; filter?: string; clipPath?: string; opacidade?: number }
function movimento(g: Grafismo, t: number, fps: number, W: number, H: number): Mov {
  const ent = g.entrada || 'mola'; const sai_ = g.saida || 'some'
  if (ent === 'mola' && sai_ === 'some') return {}
  const tl = t - g.inicio; const tf = g.fim - t
  const e = Easing.out(Easing.cubic)(Math.min(1, Math.max(0, tl / 0.38)))
  const s = Easing.in(Easing.cubic)(Math.min(1, Math.max(0, tf / 0.28)))
  const lado = Math.round(g.inicio * 10) % 2 === 0 ? 1 : -1
  const tr: string[] = []; let blur = 0; let clip: string | undefined; let op = 1
  switch (ent) {
    case 'mascara': clip = `inset(0 ${((1 - e) * 100).toFixed(1)}% 0 0)`; break
    case 'desfoque': blur += (1 - e) * 16; tr.push(`scale(${1.18 - 0.18 * e})`); op *= e; break
    case 'deslize': tr.push(`translateX(${(1 - e) * lado * W * 0.28}px)`); blur += (1 - e) * 6; op *= Math.min(1, e * 1.6); break
    case 'elastico': { const m = tl < 0 ? 0 : spring({ frame: Math.round(tl * fps), fps, config: { damping: 7, stiffness: 220, mass: 0.7 } }); tr.push(`scale(${0.35 + 0.65 * m})`); op *= Math.min(1, m * 2); break }
    case 'cair': tr.push(`translateY(${-(1 - e) * H * 0.07}px) rotate(${(1 - e) * -5 * lado}deg)`); op *= e; break
    case 'subir': tr.push(`translateY(${(1 - e) * H * 0.06}px)`); op *= e; break
  }
  if (tf < 0.28) {
    switch (sai_) {
      case 'sobe': tr.push(`translateY(${-(1 - s) * H * 0.04}px)`); op *= s; break
      case 'mascara': clip = `inset(0 0 0 ${((1 - s) * 100).toFixed(1)}%)`; break
      case 'encolhe': tr.push(`scale(${0.8 + 0.2 * s})`); op *= s; break
      case 'desfoque': blur += (1 - s) * 14; op *= s; break
      case 'deslize': tr.push(`translateX(${-(1 - s) * lado * W * 0.25}px)`); op *= s; break
      default: op *= s
    }
  }
  return { transform: tr.length ? tr.join(' ') : undefined, filter: blur > 0.3 ? `blur(${blur.toFixed(1)}px)` : undefined, clipPath: clip, opacidade: op }
}

// painel > 0 (fase C): o bloco de layout atual é o painel marinho no alto; peito e topo entram centralizados nele (fração da altura)
// painelEsq > 0 (09/11): layout composto em trecho só de rosto no 16:9 — o rosto fica na coluna da direita e os gráficos entram na coluna marinho da esquerda (fração da largura)
export const Grafismos = ({ itens, t, fps, W, H, est, painel = 0, painelEsq = 0 }: { itens: Grafismo[]; t: number; fps: number; W: number; H: number; est: Estilo; painel?: number; painelEsq?: number }) => {
  const vertical = H > W
  const u = vertical ? W / 1080 : (H / 1080) * 0.85
  const c: Ctx = { t, fps, u, W, H, vertical, est }
  const topo = { topo: vertical ? 0.075 : 0.07, peito: vertical ? 0.545 : 0.6 }
  return <>{itens.map((g, i) => {
    if (t < g.inicio - 0.01 || t > g.fim) return null
    const sai = interpolate(t, [g.fim - 0.2, g.fim], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
    const noPainel = painel > 0 && !g.tela_cheia && g.posicao !== 'centro'
    const painel_ = !noPainel && g.tipo === 'cartoes' && g.posicao === 'topo'
    const fundo = g.tela_cheia ? interpolate(t, [g.inicio, g.inicio + 0.15, g.fim - 0.15, g.fim], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : 0
    const desce = painel_ ? rampa(t - g.inicio, 0, 0.3) : 1
    const naColuna = painelEsq > 0 && !g.tela_cheia
    const zona: React.CSSProperties = naColuna
      ? (g.posicao === 'topo' ? { justifyContent: 'flex-start', alignItems: 'center', width: W * painelEsq, right: 'auto', paddingTop: H * 0.07 }
        : { justifyContent: 'center', alignItems: 'center', width: W * painelEsq, right: 'auto', paddingBottom: H * 0.06 })
      : noPainel
      ? (g.posicao === 'topo' ? { justifyContent: 'flex-start', alignItems: 'center', height: H * painel, bottom: 'auto', paddingTop: H * 0.03 }   // topo no alto do painel, peito no meio dele
        : { justifyContent: 'center', alignItems: 'center', height: H * painel, bottom: 'auto', paddingTop: H * 0.06 })
      : g.posicao === 'centro' || g.tela_cheia
      ? { justifyContent: 'center', alignItems: 'center', paddingBottom: H * 0.12 }
      : { justifyContent: 'flex-start', alignItems: 'center', paddingTop: H * (g.posicao === 'topo' ? topo.topo : topo.peito) }
    const mov = movimento(g, t, fps, W, H)
    return <AbsoluteFill key={i}>
      {g.tela_cheia && <AbsoluteFill style={{ opacity: fundo, background: `radial-gradient(circle at 50% 44%, rgba(247,150,21,0.20), rgba(0,9,33,0) 42%), ${est.cor_fundo}` }} />}
      {painel_ && <div style={{ position: 'absolute', left: 0, top: 0, width: '100%', height: H * (vertical ? 0.33 : 0.42), opacity: sai, transform: `translateY(${(desce - 1) * H * 0.33}px)`,
        background: `radial-gradient(circle at 50% 60%, rgba(247,150,21,0.16), rgba(0,9,33,0) 50%), ${est.cor_fundo}`, borderBottom: `3px solid ${est.cor_destaque}` }} />}
      <AbsoluteFill style={{ ...zona, opacity: mov.opacidade ?? sai, transform: mov.transform, filter: mov.filter, clipPath: mov.clipPath, fontFamily: 'InterGS, Inter, sans-serif', paddingTop: painel_ ? H * (vertical ? 0.06 : 0.05) : (zona.paddingTop as number | undefined) }}>
        <Conteudo g={g} c={naColuna ? { ...c, W: W * painelEsq } : c} />
      </AbsoluteFill>
    </AbsoluteFill>
  })}</>
}
