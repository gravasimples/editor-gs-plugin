import { AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, Series, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig, Easing } from 'remotion'
import type { MontagemProps } from './tipos'
import type { CSSProperties } from 'react'
import { Grafismos, Ondas } from './Grafismos'
import { BarraPassos, CamadaLayout, Cortina, PAINEL_FRAC, blocoEm, colunaEsquerda } from './Layout'
import type { LayoutCfg } from './tipos'
import { camera as camaraDe, transformCamera, filtroCamera, LuzCamera } from './Camera'
import { LegendaCinetica } from './LegendaCinetica'

// a barra de passos acompanha os blocos de tela (tutorial, tela, aula); sem nenhum bloco de tela, vale o vídeo todo
const TELA_MODOS = ['tutorial', 'tela', 'aula']
const passosVisiveis = (lay: LayoutCfg, t: number) => !lay.blocos.some((b) => TELA_MODOS.includes(b.modo)) || TELA_MODOS.includes(blocoEm(t, lay.blocos)?.modo || 'cheio')

const fontes = `
@font-face { font-family: 'InterGS'; font-weight: 800; src: url('${staticFile('fontes/Inter-ExtraBold.ttf')}') format('truetype'); }
@font-face { font-family: 'InterGS'; font-weight: 700; src: url('${staticFile('fontes/Inter-Bold.ttf')}') format('truetype'); }
@font-face { font-family: 'InterGS'; font-weight: 400; src: url('${staticFile('fontes/Inter-Regular.ttf')}') format('truetype'); }
`

function escalaZoom(t: number, p: MontagemProps): number {
  if (!p.zoom.ativo) return 1
  if (p.ritmo_zoom_s && p.ritmo_zoom_s > 0) {   // pattern interrupt: enquadramento alterna a cada N s (independe das frases)
    const i = Math.floor(Math.max(0, t) / p.ritmo_zoom_s); const ini = i * p.ritmo_zoom_s
    const alvo = i % 2 === 1 ? p.zoom.fator : 1; const anterior = i === 0 ? 1 : ((i - 1) % 2 === 1 ? p.zoom.fator : 1)
    return interpolate(t, [ini, ini + 0.3], [anterior, alvo], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) })
  }
  if (p.segmentos.length === 0) return 1
  const i = p.segmentos.findIndex(s => t >= s.inicio && t < s.fim + 0.25)
  if (i < 0) return 1
  const s = p.segmentos[i]
  const alvo = p.zoom.alternar ? (i % 2 === 1 ? p.zoom.fator : 1) : p.zoom.fator
  const anterior = i === 0 ? 1 : (p.zoom.alternar ? ((i - 1) % 2 === 1 ? p.zoom.fator : 1) : p.zoom.fator)
  const rampa = 0.35
  return interpolate(t, [s.inicio, s.inicio + rampa], [anterior, alvo], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) })
}

function opacidadeClarao(t: number, p: MontagemProps): number {
  if (!p.clarao.ativo) return 0
  let o = 0
  for (const c of p.cortes_s) {
    if (t >= c && t <= c + p.clarao.duracao_s) o = Math.max(o, interpolate(t, [c, c + p.clarao.duracao_s], [p.clarao.opacidade, 0], { extrapolateRight: 'clamp' }))
  }
  return o
}

const Destaque = ({ texto, destaque, cor }: { texto: string; destaque: string; cor: string }) => {
  if (!destaque || !texto.toLowerCase().includes(destaque.toLowerCase())) return <>{texto}</>
  const i = texto.toLowerCase().indexOf(destaque.toLowerCase())
  return <>{texto.slice(0, i)}<span style={{ color: cor }}>{texto.slice(i, i + destaque.length)}</span>{texto.slice(i + destaque.length)}</>
}

// Gancho palavra por palavra (fase 2, 03/11/2026): cada palavra sobe com spring, 0,12 s depois da anterior; a palavra do destaque fica laranja
const PalavraAPalavra = ({ texto, destaque, cor, tv, fps }: { texto: string; destaque: string; cor: string; tv: number; fps: number }) => {
  const limpa = (w: string) => w.toLowerCase().replace(/[.,!?:;"']/g, '')
  const alvo = (destaque || '').split(/\s+/).map(limpa).filter(Boolean)
  return <>{texto.split(/\s+/).filter(Boolean).map((w, i) => {
    const f = Math.round((tv - i * 0.12) * fps)
    const e = f < 0 ? 0 : spring({ frame: f, fps, config: { damping: 12, stiffness: 200, mass: 0.5 } })
    return <span key={i} style={{ display: 'inline-block', opacity: Math.min(1, e), transform: `translateY(${(1 - e) * 24}px) scale(${0.7 + 0.3 * e})`, color: alvo.includes(limpa(w)) ? cor : undefined, marginRight: '0.25em' }}>{w}</span>
  })}</>
}

// Vídeo base: o arquivo cortado (render) ou, só na prévia do editor manual (12/11/2026), os trechos da EDL editada tocados direto do bruto
const VideoBase = ({ p, muted, style }: { p: MontagemProps; muted?: boolean; style: CSSProperties }) => {
  const { fps } = useVideoConfig()
  const pv = p.previa_trechos
  if (!pv || !pv.trechos.length) return <OffthreadVideo src={staticFile(`render/${p.video}`)} muted={muted} style={style} />
  return <Series>{pv.trechos.map((t, i) => {
    const a = Math.round(t.inicio * fps), b = Math.round(t.fim * fps)
    return <Series.Sequence key={i} durationInFrames={Math.max(1, b - a)}><OffthreadVideo src={pv.src} startFrom={a} endAt={b} muted={muted} style={style} /></Series.Sequence>
  })}</Series>
}

export const Montagem: React.FC<MontagemProps> = (p) => {
  const frame = useCurrentFrame(); const { fps, width, height } = useVideoConfig()
  const t = frame / fps
  const vertical = height > width
  const mudaOrientacao = !!(p.largura_origem && p.altura_origem) && ((p.largura_origem! > p.altura_origem!) !== (width > height))
  const vin = p.vinheta && p.vinheta.ativo ? p.vinheta : null
  const atraso = vin ? vin.duracao_s : 0          // o vídeo (e o áudio dele) começa depois da vinheta
  const tv = t - atraso                            // tempo relativo ao vídeo cortado
  const fimVideo = p.duracao_s + atraso
  const telaFinal = p.tela_final && p.tela_final.ativo ? p.tela_final : null
  const inicioFinal = fimVideo
  const opVin = vin ? interpolate(t, [0, 0.15, vin.duracao_s - 0.3, vin.duracao_s], [1, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : 0
  const barraVin = vin ? interpolate(t, [0.1, vin.duracao_s * 0.6], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }) : 0
  const tituloVin = vin ? interpolate(t, [0.05, 0.45], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }) : 0
  const ter = p.terco && p.terco.texto ? p.terco : null
  const tTer = ter ? tv - ter.inicio_s : -1
  const opTer = ter ? interpolate(tTer, [0, 0.3, ter.duracao_s - 0.3, ter.duracao_s], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : 0
  const xTer = ter ? interpolate(tTer, [0, 0.45], [-60, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }) : 0
  const fi = p.frase_impacto
  const opFrase = fi ? interpolate(tv, [0, 0.35, fi.duracao_s - 0.4, fi.duracao_s], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : 0
  const yFrase = fi ? interpolate(tv, [0, 0.45], [40, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }) : 0
  // tela final (polimento 03/11): o fundo cobre o vídeo em 0,25 s e só depois o texto entra (antes título e vídeo ficavam sobrepostos, "fantasma")
  const opFinal = telaFinal ? interpolate(t, [inicioFinal - 0.25, inicioFinal], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : 0
  const entraFinal = (atraso: number) => interpolate(t, [inicioFinal + atraso, inicioFinal + atraso + 0.35], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) })
  const cam = p.camera && p.camera.planos && p.camera.planos.length ? camaraDe(tv, p.camera.planos, width) : null
  const escala = cam ? cam.escala : escalaZoom(tv, p)
  const clarao = cam ? 0 : opacidadeClarao(tv, p)
  const origem = p.camera && p.camera.origem ? `${(p.camera.origem.x * 100).toFixed(1)}% ${(p.camera.origem.y * 100).toFixed(1)}%` : '50% 45%'
  const tamTitulo = vertical ? width * 0.085 : width * 0.05
  const lay = p.layout && p.layout.blocos && p.layout.blocos.length ? p.layout : null
  const modoAgora = lay ? (blocoEm(tv, lay.blocos)?.modo ?? 'cheio') : 'cheio'
  // camada (12/11/2026, exportação para o CapCut): 'base' = vídeo, layout e câmera; 'graficos' = textos, grafismos, b-roll em janela e cartelas sobre fundo transparente; 'legenda' = só a legenda cinética
  const camada = p.camada || 'tudo'
  const comBase = camada === 'tudo' || camada === 'base'; const comGraf = camada === 'tudo' || camada === 'graficos'; const comLeg = camada === 'tudo' || camada === 'legenda'
  return (
    <AbsoluteFill style={{ backgroundColor: comBase ? p.estilo.cor_fundo : 'transparent', fontFamily: 'InterGS, Inter, sans-serif' }}>
      <style>{fontes}</style>
      {comBase && <Sequence from={Math.round(atraso * fps)} durationInFrames={Math.ceil(p.duracao_s * fps)}>
        {mudaOrientacao && (!lay || modoAgora === 'cheio') && (
          <AbsoluteFill>
            {p.video_fundo
              ? <OffthreadVideo src={staticFile(`render/${p.video_fundo}`)} muted style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scale(1.1)' }} />
              : <VideoBase p={p} muted style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'blur(28px) brightness(0.55)', transform: 'scale(1.1)' }} />}
          </AbsoluteFill>
        )}
        {lay ? (
          <AbsoluteFill style={cam ? { transform: `translate(${cam.tx}px, ${cam.ty}px) rotate(${cam.rot}deg)`, filter: filtroCamera(cam) } : undefined}>
            <CamadaLayout cfg={lay} video={p.video} t={tv} W={width} H={height} escala={escala} est={p.estilo} mudaOrientacao={mudaOrientacao} />
          </AbsoluteFill>
        ) : (
          <AbsoluteFill style={{ transform: cam ? transformCamera(cam) : `scale(${escala})`, transformOrigin: origem, filter: cam ? filtroCamera(cam) : undefined }}>
            <VideoBase p={p} style={{ width: '100%', height: '100%', objectFit: mudaOrientacao ? 'contain' : 'cover' }} />
          </AbsoluteFill>
        )}
        {cam && <LuzCamera c={cam} cor={p.estilo.cor_destaque} />}
      </Sequence>}
      {comGraf && fi && opFrase > 0 && (
        <AbsoluteFill style={{ justifyContent: 'flex-start', alignItems: 'center', paddingTop: vertical ? height * 0.1 : height * 0.06, opacity: opFrase, transform: `translateY(${yFrase}px)` }}>
          <div style={{ background: 'rgba(0,9,33,0.78)', borderRadius: 20, padding: `${tamTitulo * 0.35}px ${tamTitulo * 0.6}px`, maxWidth: '86%', textAlign: 'center',
            fontWeight: 800, fontSize: tamTitulo, lineHeight: 1.1, color: p.estilo.cor_texto, textTransform: 'uppercase' }}>
            {fi.animacao === 'palavra' ? <PalavraAPalavra texto={fi.texto} destaque={fi.destaque} cor={p.estilo.cor_destaque} tv={tv} fps={fps} /> : <Destaque texto={fi.texto} destaque={fi.destaque} cor={p.estilo.cor_destaque} />}
          </div>
        </AbsoluteFill>
      )}
      {comGraf && ter && opTer > 0 && (
        <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'flex-start', padding: vertical ? `0 6% ${height * 0.3}px` : `0 5% ${height * 0.12}px`, opacity: opTer, transform: `translateX(${xTer}px)` }}>
          <div style={{ display: 'flex', alignItems: 'stretch', borderRadius: 16, overflow: 'hidden', background: 'rgba(0,9,33,0.82)', maxWidth: '80%' }}>
            <div style={{ width: tamTitulo * 0.16, background: `linear-gradient(180deg, ${p.estilo.cor_destaque}, #E9760D)` }} />
            <div style={{ padding: `${tamTitulo * 0.22}px ${tamTitulo * 0.45}px` }}>
              <div style={{ fontWeight: 800, fontSize: tamTitulo * 0.62, lineHeight: 1.1, color: p.estilo.cor_texto }}>{ter.texto}</div>
              {ter.sub && <div style={{ fontWeight: 400, fontSize: tamTitulo * 0.42, lineHeight: 1.2, color: '#A7ACBD', marginTop: tamTitulo * 0.08 }}>{ter.sub}</div>}
            </div>
          </div>
        </AbsoluteFill>
      )}
      {(p.broll || []).map((b, i) => {
        const ini = Math.round((b.inicio + atraso) * fps); const dur = Math.max(1, Math.round(b.duracao_s * fps))
        const tb = tv - b.inicio; if (tb < 0 || tb > b.duracao_s) return null
        if (camada !== 'tudo' && !(camada === 'graficos' && b.modo === 'janela')) return null   // b-roll cheio vai como clipe próprio no CapCut
        const op = interpolate(tb, [0, 0.25, b.duracao_s - 0.25, b.duracao_s], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
        const esc = interpolate(tb, [0, b.duracao_s], [1, 1.08], { extrapolateRight: 'clamp' })
        const janela = b.modo === 'janela'
        const box: React.CSSProperties = janela ? { position: 'absolute', left: '5%', top: vertical ? '12.5%' : '11%', width: '90%', height: vertical ? '38%' : '52%', borderRadius: 20, overflow: 'hidden', boxShadow: '0 12px 40px rgba(0,0,0,0.45)' } : { position: 'absolute', inset: 0 }  // abaixo da pílula de capítulo
        const media: React.CSSProperties = { width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${esc})` }
        return <Sequence key={`b${i}`} from={ini} durationInFrames={dur}><AbsoluteFill style={{ opacity: op }}><div style={box}>
          {b.video ? <OffthreadVideo src={staticFile(`render/${b.arquivo}`)} muted style={media} /> : <Img src={staticFile(`render/${b.arquivo}`)} style={media} />}
        </div></AbsoluteFill></Sequence>
      })}
      {(!comGraf || (p.grafismos && p.grafismos.length) ? [] : (p.palavras_chave || [])).map((k, i) => {
        const tk = tv - k.inicio; const dur = Math.max(0.6, k.fim - k.inicio); if (tk < 0 || tk > dur) return null
        const entrada = spring({ frame: Math.round(tk * fps), fps, config: { damping: 12, stiffness: 180, mass: 0.6 } })
        const saida = interpolate(tk, [dur - 0.2, dur], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
        const comFrase = fi ? tv < fi.duracao_s : false
        return <AbsoluteFill key={`k${i}`} style={{ justifyContent: 'flex-start', alignItems: 'center', paddingTop: vertical ? height * (comFrase ? 0.33 : 0.17) : height * (comFrase ? 0.27 : 0.1), opacity: Math.min(entrada, saida) }}>
          <div style={{ transform: `scale(${0.6 + 0.4 * entrada}) rotate(${(1 - entrada) * -4}deg)`, background: `linear-gradient(90deg, ${p.estilo.cor_destaque}, #E9760D)`, color: p.estilo.cor_fundo, fontWeight: 800,
            fontSize: tamTitulo * 0.95, lineHeight: 1, padding: `${tamTitulo * 0.28}px ${tamTitulo * 0.55}px`, borderRadius: 999, textTransform: 'uppercase', letterSpacing: 1, boxShadow: '0 10px 30px rgba(0,0,0,0.35)' }}>{k.texto}</div>
        </AbsoluteFill>
      })}
      {comLeg && p.legenda_cinetica && p.legenda_cinetica.linhas.length > 0 && tv >= 0 && tv <= p.duracao_s && (
        <LegendaCinetica cfg={p.legenda_cinetica} t={tv} H={height} oculta={(p.grafismos || []).some((g) => g.tela_cheia && tv >= g.inicio && tv <= g.fim)} />
      )}
      {comGraf && p.grafismos && p.grafismos.length > 0 && tv >= 0 && tv <= p.duracao_s && <Grafismos itens={p.grafismos} t={tv} fps={fps} W={width} H={height} est={p.estilo} painel={modoAgora === 'painel' ? (vertical ? PAINEL_FRAC : 0.3) : 0} painelEsq={colunaEsquerda(lay, tv, vertical)} />}
      {(comGraf ? p.capitulos || [] : []).map((c, i) => {
        const tc = tv - c.inicio; const dur = 2.6; if (tc < 0 || tc > dur) return null
        const x = interpolate(tc, [0, 0.35], [-80, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) })
        const op = interpolate(tc, [0, 0.25, dur - 0.3, dur], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
        const comFraseC = fi ? tv < fi.duracao_s : false  // com a frase de impacto na tela, a pílula desce para baixo dela
        return <AbsoluteFill key={`c${i}`} style={{ justifyContent: 'flex-start', alignItems: 'flex-start', padding: vertical ? `${height * (comFraseC ? 0.245 : 0.045)}px 5%` : `${height * (comFraseC ? 0.2 : 0.04)}px 4%`, opacity: op, transform: `translateX(${x}px)` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: tamTitulo * 0.3, background: 'rgba(0,9,33,0.82)', borderRadius: 999, padding: `${tamTitulo * 0.18}px ${tamTitulo * 0.45}px ${tamTitulo * 0.18}px ${tamTitulo * 0.2}px` }}>
            {c.numero != null && <div style={{ background: p.estilo.cor_destaque, color: p.estilo.cor_fundo, fontWeight: 800, fontSize: tamTitulo * 0.5, borderRadius: 999, padding: `${tamTitulo * 0.08}px ${tamTitulo * 0.3}px` }}>{c.numero}{c.total ? `/${c.total}` : ''}</div>}
            <div style={{ fontWeight: 700, fontSize: tamTitulo * 0.52, color: p.estilo.cor_texto }}>{c.texto}</div>
          </div>
        </AbsoluteFill>
      })}
      {comGraf && p.barra_progresso && tv >= 0 && tv <= p.duracao_s && (
        <div style={{ position: 'absolute', left: 0, bottom: 0, height: Math.max(5, Math.round(height * 0.006)), width: `${(tv / p.duracao_s) * 100}%`, background: `linear-gradient(90deg, ${p.estilo.cor_destaque}, #E9760D)` }} />
      )}
      {comGraf && lay && lay.passos && lay.passos.length > 0 && tv >= 0 && tv <= p.duracao_s && passosVisiveis(lay, tv) && <BarraPassos passos={lay.passos} t={tv} W={width} H={height} est={p.estilo} />}
      {comGraf && lay && lay.cortinas_s.length > 0 && <Cortina instantes={lay.cortinas_s} t={tv} est={p.estilo} />}
      {(camada === 'tudo' ? p.sfx || [] : []).map((e, i) => <Sequence key={`s${i}`} from={Math.round((e.inicio + atraso) * fps)} durationInFrames={Math.round(2 * fps)}><Audio src={staticFile(`sfx/${e.arquivo}`)} volume={e.volume} /></Sequence>)}
      {comGraf && clarao > 0 && <AbsoluteFill style={{ backgroundColor: 'white', opacity: clarao }} />}
      {comGraf && vin && opVin > 0 && (
        <AbsoluteFill style={{ backgroundColor: p.estilo.cor_fundo, opacity: opVin, justifyContent: 'center', alignItems: 'center', textAlign: 'center', padding: '8%' }}>
          <div style={{ fontWeight: 800, fontSize: tamTitulo * 1.05, lineHeight: 1.05, color: p.estilo.cor_texto, letterSpacing: 1, textTransform: 'uppercase', opacity: tituloVin, transform: `translateY(${(1 - tituloVin) * 30}px)` }}>
            <Destaque texto={vin.titulo} destaque={vin.destaque} cor={p.estilo.cor_destaque} />
          </div>
          <div style={{ marginTop: tamTitulo * 0.5, height: Math.max(6, tamTitulo * 0.12), width: `${barraVin * 42}%`, borderRadius: 999, background: `linear-gradient(90deg, ${p.estilo.cor_destaque}, #E9760D)` }} />
        </AbsoluteFill>
      )}
      {comGraf && telaFinal && t >= inicioFinal - 0.25 && (
        <AbsoluteFill style={{ background: telaFinal.selo ? `radial-gradient(circle at 50% 42%, rgba(247,150,21,0.16), rgba(0,9,33,0) 45%), ${p.estilo.cor_fundo}` : p.estilo.cor_fundo, opacity: opFinal, justifyContent: 'center', alignItems: 'center', textAlign: 'center', padding: '8%' }}>
          {telaFinal.selo && <div style={{ display: 'flex', alignItems: 'center', gap: tamTitulo * 0.15, marginBottom: tamTitulo * 0.45, background: 'rgba(11,25,61,0.92)', border: '1.5px solid rgba(255,255,255,0.14)', borderRadius: 999,
            padding: `${tamTitulo * 0.12}px ${tamTitulo * 0.3}px`, fontWeight: 800, fontSize: tamTitulo * 0.32, color: p.estilo.cor_texto, letterSpacing: 2, textTransform: 'uppercase', opacity: entraFinal(0) }}>
            <div style={{ width: tamTitulo * 0.14, height: tamTitulo * 0.14, borderRadius: 999, background: p.estilo.cor_destaque }} />{telaFinal.selo}</div>}
          <div style={{ fontWeight: 800, fontSize: tamTitulo * 1.15, lineHeight: 1.1, color: p.estilo.cor_texto, opacity: entraFinal(0.05), transform: `translateY(${(1 - entraFinal(0.05)) * 30}px)` }}>
            <Destaque texto={telaFinal.titulo} destaque={telaFinal.destaque} cor={p.estilo.cor_destaque} />
          </div>
          <div style={{ marginTop: tamTitulo * 0.9, background: `linear-gradient(90deg, ${p.estilo.cor_destaque}, #E9760D)`, color: p.estilo.cor_fundo, fontWeight: 800,
            fontSize: tamTitulo * 0.62, padding: `${tamTitulo * 0.35}px ${tamTitulo * 0.9}px`, borderRadius: 999, opacity: entraFinal(0.3),
            transform: `scale(${interpolate(t, [inicioFinal + 0.3, inicioFinal + 0.7], [0.85, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(1.4)) })})` }}>
            {telaFinal.chamada && <div style={{ fontWeight: 700, fontSize: tamTitulo * 0.3, letterSpacing: 1, textTransform: 'uppercase', opacity: 0.8 }}>{telaFinal.chamada}</div>}
            {telaFinal.cta}
          </div>
          {telaFinal.ondas && <div style={{ marginTop: tamTitulo * 0.7, opacity: entraFinal(0.45) }}><Ondas c={{ t, fps, u: width / 1080, W: width, H: height, vertical, est: p.estilo }} tl={t - inicioFinal} largura={width * 0.62} altura={tamTitulo * 0.9} /></div>}
          <div style={{ position: 'absolute', bottom: '7%', fontWeight: 700, fontSize: tamTitulo * 0.5, color: '#A7ACBD', letterSpacing: 2, opacity: entraFinal(0.5) }}>{telaFinal.marca}</div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  )
}
